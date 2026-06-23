(() => {
  const replacements = [
    ['Dify 权限增强版', 'MMBAI 企业版'],
    ['Dify Plus 管理台', '企业管理后台'],
    ['Dify Plus 用户管理页', '企业级用户管理页'],
    ['Dify Professional', 'MMBAI Professional'],
    ['Dify Education', 'MMBAI Education'],
    ['Dify Educational', 'MMBAI Educational'],
    ['Dify API', 'MMBAI API'],
    ['Dify 工作台', 'AI 中台'],
    ['真实 Dify 工作台', 'MMBAI 工作台'],
    ['返回 Dify', '返回 AI 中台'],
    ['Talk to Dify', 'Talk to MMBAI'],
    ['LangGenius, Inc. All rights reserved.', 'MMBAI. 保留所有权利。'],
    ['LangGenius, Inc., Contributors.', 'MMBAI, Contributors.'],
    ['LangGenius', 'MMBAI'],
    ['Dify', 'MMBAI'],
  ];

  const skipTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TEXTAREA', 'INPUT', 'CODE', 'PRE']);

  const replaceValue = (value) => {
    let next = value;
    for (const [from, to] of replacements) next = next.replaceAll(from, to);
    return next;
  };

  const rewriteTexts = () => {
    document.title = replaceValue(document.title || '');
    const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (appleTitle?.content) appleTitle.content = replaceValue(appleTitle.content);

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        const parent = node.parentElement;
        if (!parent || skipTags.has(parent.tagName) || parent.closest('[data-no-mmb-brand-patch]')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const next = replaceValue(node.nodeValue || '');
      if (next !== node.nodeValue) node.nodeValue = next;
    }

    document.querySelectorAll('img[alt*="Dify"], [aria-label*="Dify"], [title*="Dify"]').forEach((el) => {
      if (el.alt) el.alt = replaceValue(el.alt);
      if (el.getAttribute('aria-label')) el.setAttribute('aria-label', replaceValue(el.getAttribute('aria-label')));
      if (el.getAttribute('title')) el.setAttribute('title', replaceValue(el.getAttribute('title')));
    });
  };

  const run = () => requestAnimationFrame(rewriteTexts);
  run();
  document.addEventListener('DOMContentLoaded', run, { once: true });
  window.addEventListener('load', run, { once: true });

  let ticks = 0;
  const timer = setInterval(() => {
    rewriteTexts();
    ticks += 1;
    if (ticks >= 40) clearInterval(timer);
  }, 250);
})();
