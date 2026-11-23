async (page) => {
  const base = new URL(page.url()).origin
  const passed = []
  const assert = (value, message) => { if (!value) throw new Error(message) }
  const marker = `验收 ${Date.now()}`
  const browser = page.context().browser()
  const contextB = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const b = await contextB.newPage()
  async function signIn(target, account) {
    await target.getByRole('button', { name: '登录', exact: true }).click()
    await target.getByRole('button', { name: account }).click()
    await target.getByRole('dialog').getByRole('button', { name: '登录', exact: true }).click()
    await target.getByRole('button', { name: '退出登录', exact: true }).waitFor()
  }
  async function create(target, text, x, y, formats = []) {
    await target.getByRole('button', { name: '新增贴纸', exact: true }).click()
    await target.getByLabel('评论画布', { exact: true }).click({ position: { x, y } })
    const editor = target.getByRole('textbox', { name: '评论内容' })
    await editor.fill(text)
    if (formats.length) {
      await editor.press('ControlOrMeta+a')
      for (const name of formats) await target.getByRole('button', { name, exact: true }).click()
    }
    await target.getByRole('button', { name: '马上发表', exact: true }).click()
    const note = target.getByRole('article').filter({ hasText: text })
    await note.waitFor()
    return note
  }
  try {
    await page.context().clearCookies()
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(base)
    await signIn(page, '赵欣 · demo_a')
    await b.goto(base)
    await signIn(b, '王美丽 · demo_b')
    await page.getByLabel('2 人在线', { exact: true }).waitFor()
    passed.push('两个独立账号登录与在线成员')

    const positiveText = `${marker} 感谢支持，这个工具非常好用。`
    const noteA = await create(page, positiveText, 100, 650, ['加粗', '斜体', '下划线', '删除线', '无序列表'])
    const id = await noteA.getAttribute('data-note-id')
    const noteB = b.getByRole('article').filter({ hasText: positiveText })
    await noteB.waitFor()
    for (const tag of ['strong', 'em', 'u', 's', 'ul']) assert(await noteB.locator(tag).count() > 0, `${tag} 格式未同步`)
    assert(await noteB.getAttribute('data-sentiment') === 'positive', '正面情绪未识别')
    passed.push('富文本保存、实时发布和自动变色')

    await noteB.click()
    await b.getByRole('dialog', { name: '查看建议' }).waitFor()
    assert(await b.getByRole('button', { name: '保存修改' }).count() === 0, '其他用户出现编辑入口')
    await b.getByRole('button', { name: '关闭编辑器' }).click()
    const forbidden = await contextB.request.patch(`${base}/api/comments/${id}/content`, { data: { content_html: '<p>越权测试</p>', content_version: 1 } })
    assert(forbidden.status() === 403, '服务端没有拒绝越权修改')
    passed.push('只读界面与服务端作者权限')

    await noteB.getByRole('button', { name: '点赞·赵欣的贴纸', exact: true }).click()
    await noteA.getByRole('button').filter({ hasText: '1' }).waitFor()
    await noteB.getByRole('button', { name: '取消点赞·赵欣的贴纸', exact: true }).click()
    await page.waitForFunction(id => document.querySelector(`[data-note-id="${id}"] .like-button`)?.textContent.trim() === '', id)
    passed.push('跨用户点赞与取消点赞')

    await page.getByRole('button', { name: '拖动贴纸', exact: true }).click()
    await noteA.scrollIntoViewIfNeeded()
    const box = await noteA.boundingBox()
    const saved = page.waitForResponse(r => r.url().includes(`/comments/${id}/position`) && r.ok())
    await page.mouse.move(box.x + 40, box.y + 40)
    await page.mouse.down()
    await page.mouse.move(box.x + 100, box.y - 20, { steps: 8 })
    await page.mouse.up()
    await saved
    const left = await noteA.evaluate(el => el.style.left)
    await b.waitForFunction(({ id, left }) => document.querySelector(`[data-note-id="${id}"]`)?.style.left === left, { id, left })
    await b.reload()
    await b.getByRole('article').filter({ hasText: positiveText }).waitFor()
    passed.push('指针拖动同步与刷新恢复')

    await page.getByRole('button', { name: '智能整理', exact: true }).click()
    const before = await (await page.request.get(`${base}/api/board`)).json()
    const positions = await page.getByRole('article').evaluateAll(els => els.map(el => ({ group: el.dataset.sentiment, left: el.offsetLeft, top: el.offsetTop, height: el.offsetHeight })))
    for (const category of ['positive', 'neutral', 'negative']) {
      const group = positions.filter(p => p.group === category).sort((a, b) => a.top - b.top)
      for (let i = 1; i < group.length; i++) assert(group[i].left === group[0].left && group[i].top >= group[i - 1].top + group[i - 1].height + 20, '分类布局出现重叠')
    }
    await page.getByRole('button', { name: '还原布局', exact: true }).click()
    const after = await (await page.request.get(`${base}/api/board`)).json()
    assert(JSON.stringify(before) === JSON.stringify(after), '智能整理修改了共享数据')
    passed.push('情绪概览、无重叠整理和还原')

    await page.context().setOffline(true)
    await page.getByText('连接中断，正在重连…', { exact: true }).waitFor()
    const negativeText = `${marker} 这个工具很差，经常闪退，令人失望。`
    await create(b, negativeText, 550, 650, ['有序列表'])
    await page.context().setOffline(false)
    await page.getByRole('article').filter({ hasText: negativeText }).waitFor()
    const negative = page.getByRole('article').filter({ hasText: negativeText })
    assert(await negative.getAttribute('data-sentiment') === 'negative', '负面情绪未识别')
    assert(await negative.locator('ol').count() > 0, '有序列表未保存')
    passed.push('断网恢复、补齐离线变化、有序列表')

    const duplicate = await page.context().newPage()
    await duplicate.goto(base)
    await duplicate.getByLabel('2 人在线', { exact: true }).waitFor()
    await duplicate.close()
    await page.getByLabel('2 人在线', { exact: true }).waitFor()
    passed.push('同账号多个标签页去重')

    for (const width of [1820, 1440, 1200, 1024, 768, 390, 375]) {
      await page.setViewportSize({ width, height: 900 })
      const toolbar = await page.getByRole('navigation', { name: '画布工具' }).boundingBox()
      assert(toolbar.x >= 0 && toolbar.x + toolbar.width <= width + 1, `${width}px 工具栏超出屏幕`)
      const labels = await page.locator('.emotion-bar > span').evaluateAll(els => els.every(el => el.scrollWidth <= el.clientWidth + 1))
      assert(labels, `${width}px 情绪标签被截断`)
    }
    passed.push('7 个桌面与手机断点')
    await contextB.close()
    await page.getByLabel('1 人在线', { exact: true }).waitFor()
    await page.getByRole('button', { name: '退出登录', exact: true }).click()
    await page.getByRole('button', { name: '登录', exact: true }).waitFor()
    await page.getByRole('button', { name: '登录', exact: true }).click()
    const modal = await page.getByRole('dialog').boundingBox()
    assert(modal.x >= 0 && modal.x + modal.width <= 376, '手机登录弹窗超出屏幕')
    await page.getByRole('button', { name: '关闭登录' }).click()
    passed.push('退出在线状态与手机登录弹窗')
    return { passed }
  } finally {
    await page.context().setOffline(false)
    await contextB.close().catch(() => {})
  }
}
