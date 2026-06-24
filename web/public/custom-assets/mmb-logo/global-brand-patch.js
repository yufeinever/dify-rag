(() => {
  const BRAND_LABEL = 'AI中台';
  const BRAND_NAME = 'MMB-AI';
  const BRAND_LOGO_ALT = `${BRAND_NAME} logo`;
  const replacements = [
    ['Dify 权限增强版', 'MMBAI 企业版'],
    ['Dify Plus 管理台', '企业管理后台'],
    ['Dify Plus 用户管理页', '企业级用户管理页'],
    ['Dify Professional', 'MMBAI Professional'],
    ['Dify Education', 'MMBAI Education'],
    ['Dify Educational', 'MMBAI Educational'],
    ['Dify API', 'MMBAI API'],
    ['Dify 工作台', 'AI中台'],
    ['真实 Dify 工作台', 'MMBAI 工作台'],
    ['返回 Dify', '返回 AI中台'],
    ['Talk to Dify', 'Talk to MMB-AI'],
    ['工作室 - Dify', `工作室 - ${BRAND_NAME}`],
    ['知识库 - Dify', `知识库 - ${BRAND_NAME}`],
    ['工具 - Dify', `工具 - ${BRAND_NAME}`],
    ['登录 mmb - Dify', `登录 MMBAI - ${BRAND_NAME}`],
    ['Dify Dify logo', `${BRAND_LABEL} ${BRAND_LOGO_ALT}`],
    ['Dify logo', BRAND_LOGO_ALT],
    ['LangGenius, Inc. All rights reserved.', 'MMBAI. 保留所有权利。'],
    ['LangGenius, Inc., Contributors.', 'MMBAI, Contributors.'],
    ['LangGenius', 'MMBAI'],
    ['Dify', BRAND_LABEL],
  ];

  const skipTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TEXTAREA', 'INPUT', 'CODE', 'PRE']);

  const replaceValue = (value) => {
    let next = value;
    for (const [from, to] of replacements)
      next = next.replaceAll(from, to);
    return next;
  };

  const patchHeaderBrand = () => {
    const appLinks = Array.from(document.querySelectorAll('a[href="/apps"]'));
    const brandLink = appLinks.find(link => link.closest('h1'));
    if (!brandLink)
      return;

    brandLink.setAttribute('aria-label', BRAND_LABEL);
    brandLink.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const next = replaceValue(node.nodeValue || '');
        node.nodeValue = next.trim() ? next : BRAND_LABEL;
      }
    });

    const logo = brandLink.querySelector('img');
    if (logo) {
      logo.alt = BRAND_LOGO_ALT;
      if (logo.title)
        logo.title = replaceValue(logo.title);
    }
  };

  const rewriteTexts = () => {
    document.title = replaceValue(document.title || '');
    const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (appleTitle?.content)
      appleTitle.content = replaceValue(appleTitle.content);

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        const parent = node.parentElement;
        if (!parent || skipTags.has(parent.tagName) || parent.closest('[data-no-mmb-brand-patch]'))
          return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const nodes = [];
    while (walker.nextNode())
      nodes.push(walker.currentNode);

    for (const node of nodes) {
      const next = replaceValue(node.nodeValue || '');
      if (next !== node.nodeValue)
        node.nodeValue = next;
    }

    document.querySelectorAll('img[alt*="Dify"], [aria-label*="Dify"], [title*="Dify"]').forEach((el) => {
      if (el.alt)
        el.alt = replaceValue(el.alt);
      if (el.getAttribute('aria-label'))
        el.setAttribute('aria-label', replaceValue(el.getAttribute('aria-label')));
      if (el.getAttribute('title'))
        el.setAttribute('title', replaceValue(el.getAttribute('title')));
    });

    patchHeaderBrand();
  };

  let raf = 0;
  const run = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(rewriteTexts);
  };

  run();
  document.addEventListener('DOMContentLoaded', run, { once: true });
  window.addEventListener('load', run, { once: true });
  window.addEventListener('popstate', run);

  const { pushState, replaceState } = window.history;
  window.history.pushState = function (...args) {
    const ret = pushState.apply(this, args);
    run();
    return ret;
  };
  window.history.replaceState = function (...args) {
    const ret = replaceState.apply(this, args);
    run();
    return ret;
  };

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['alt', 'aria-label', 'title'],
  });

  let ticks = 0;
  const timer = setInterval(() => {
    rewriteTexts();
    ticks += 1;
    if (ticks >= 80) {
      clearInterval(timer);
      observer.disconnect();
    }
  }, 250);
})();
