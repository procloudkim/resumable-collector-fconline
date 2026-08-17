from __future__ import annotations
"""
Lightweight Selenium helpers shared by crawlers.

Notes
- Uses webdriver-manager to simplify local driver setup.
- Defaults to headless Chrome with sane flags for crawling.
- Keep import guards so the rest of the project works without Selenium installed.
"""
from typing import Optional, Sequence


def create_driver(headless: bool = True, user_agent: Optional[str] = None):  # type: ignore[override]
    try:
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
        from selenium.webdriver.chrome.service import Service  # type: ignore
        from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Selenium/Chrome not available. pip install selenium webdriver-manager") from e

    import os
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    # Stable flags for CI/crawling
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,2000")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    # Prefer locally provided driver if available to avoid network downloads
    chromedriver_path = os.getenv("CHROMEDRIVER")
    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver


def wait_for_any_css(driver, selectors: Sequence[str], timeout: int = 10):  # type: ignore[override]
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore

    def any_present(_):
        for sel in selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    return True
            except Exception:
                continue
        return False

    WebDriverWait(driver, timeout).until(any_present)
    return True


def click_first_by_text(driver, texts: Sequence[str], timeout: int = 5) -> bool:  # type: ignore[override]
    """Click the first element whose visible text contains any of the given snippets.

    Tries <a> and <button> primarily. Returns True on success, False otherwise.
    """
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore

    for t in texts:
        xpath = f"//a[contains(normalize-space(.), '{t}')] | //button[contains(normalize-space(.), '{t}')]"
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            el.click()
            return True
        except Exception:
            continue
    return False


def apply_stealth(driver, user_agent: Optional[str] = None):  # type: ignore[override]
    """Apply light anti-bot fingerprints via Chrome DevTools.

    - Hide navigator.webdriver
    - Spoof languages/plugins/platform where possible
    - Override UA if provided
    """
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    "Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR','ko','en-US','en']});"
                    "Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});"
                )
            },
        )
        if user_agent:
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})
    except Exception:
        pass


def detect_captcha(html: str) -> bool:
    if not html:
        return False
    lower = html.lower()
    keywords = [
        "captcha", "자동입력", "보안문자", "i am not a robot", "cloudflare", "봇이 아닌지",
    ]
    return any(k in lower for k in keywords)


def install_overlay_blocker(driver, selectors: Sequence[str]):  # type: ignore[override]
    """Persistently hide/remove annoying overlays/banners.

    - Injects a <style> that hides selectors via display:none and pointer-events:none
    - Adds a MutationObserver to remove any future nodes matching selectors
    """
    sel_list = ",".join(selectors)
    js = f"""
      (function(){{
        try {{
          // 1) CSS kill switch
          var sid = 'fc_overlay_blocker_style';
          var old = document.getElementById(sid);
          if (old && old.parentNode) old.parentNode.removeChild(old);
          var st = document.createElement('style');
          st.id = sid;
          st.type = 'text/css';
          st.textContent = '{sel_list}'.replace(/,/g,', ') + ' {{ display:none !important; pointer-events:none !important; visibility:hidden !important; }}';
          document.head.appendChild(st);

          // 2) Remove existing nodes immediately
          document.querySelectorAll('{sel_list}').forEach(function(el) {{ try {{ el.remove(); }} catch (e) {{}} }});

          // 3) Mutation observer to remove future overlays
          var oid = 'fc_overlay_blocker_observer';
          if (!window[oid]) {{
            var obs = new MutationObserver(function(muts) {{
              muts.forEach(function(m) {{
                if (m.addedNodes && m.addedNodes.length) {{
                  m.addedNodes.forEach(function(n) {{
                    try {{
                      if (n.matches && n.matches('{sel_list}')) {{ n.remove(); return; }}
                      if (n.querySelectorAll) {{ n.querySelectorAll('{sel_list}').forEach(function(el) {{ el.remove(); }}); }}
                    }} catch(e) {{}}
                  }});
                }}
              }});
            }});
            obs.observe(document.documentElement || document.body, {{ childList:true, subtree:true }});
            window[oid] = obs;
          }}
        }} catch (e) {{}}
      }})();
    """
    try:
        driver.execute_script(js)
    except Exception:
        pass


def remove_elements(driver, selectors: Sequence[str]):  # type: ignore[override]
    sel_list = ",".join(selectors)
    try:
        driver.execute_script(
            "document.querySelectorAll(arguments[0]).forEach(e=>{try{e.remove()}catch(_){}})",
            sel_list,
        )
    except Exception:
        pass


def aggressive_kill_overlays(driver, selectors: Sequence[str], duration_ms: int = 10000, period_ms: int = 300):  # type: ignore[override]
    """Repeatedly hide/remove overlays and try their built-in close buttons.

    - Forces display:none/visibility:hidden/pointer-events:none with !important
    - Attempts to click close buttons inside known containers
    - Repeats for duration_ms every period_ms to catch re-appearing banners
    """
    sel_list = ",".join(selectors)
    js = f"""
      (function(){{
        var sel = '{sel_list}';
        var started = Date.now();
        function step(){{
          try {{
            // style-kill + remove
            document.querySelectorAll(sel).forEach(function(el){{
              try{{
                el.style.setProperty('display','none','important');
                el.style.setProperty('visibility','hidden','important');
                el.style.setProperty('pointer-events','none','important');
                // try close buttons
                var btn = el.querySelector('.i_after button, .i_before button, button');
                if (btn) {{ try {{ btn.click(); }} catch(e) {{}} }}
                // final remove
                if (el.parentNode) el.parentNode.removeChild(el);
              }}catch(_e){{}}
            }});
          }} catch(_e) {{}}
          if (Date.now() - started < {duration_ms}) {{
            setTimeout(step, {period_ms});
          }}
        }}
        step();
      }})();
    """
    try:
        driver.execute_script(js)
    except Exception:
        pass


def preinstall_overlay_kill_on_new_document(driver, selectors: Sequence[str]):  # type: ignore[override]
    """Register a script via DevTools to hide overlays from T=0 (before site JS runs).

    This injects a <style> as soon as possible and sets up an early MutationObserver
    so the banner never gets a chance to occupy the viewport during initial load.
    """
    sel_list = ",".join(selectors)
    source = f"""
      (function(){{
        try {{
          var sid = 'fc_overlay_pre_style';
          function ensureStyle(){{
            try{{
              var st = document.getElementById(sid);
              if (!st) {{
                st = document.createElement('style');
                st.id = sid;
                st.type = 'text/css';
                st.textContent = '{sel_list}'.replace(/,/g,', ') + ' {{ display:none !important; visibility:hidden !important; pointer-events:none !important; }}';
                (document.head || document.documentElement).appendChild(st);
              }}
            }}catch(_e){{}}
          }}
          ensureStyle();
          // Early observer to catch nodes before paint
          try {{
            var obs = new MutationObserver(function(muts){{
              muts.forEach(function(m){{
                (m.addedNodes||[]).forEach(function(n){{
                  try{{
                    if (n.matches && n.matches('{sel_list}')) {{ n.remove(); return; }}
                    if (n.querySelectorAll) n.querySelectorAll('{sel_list}').forEach(function(el){{ el.remove(); }});
                  }}catch(_e){{}}
                }});
              }});
            }});
            obs.observe(document.documentElement || document, {{childList:true, subtree:true}});
          }} catch(_e) {{}}
          document.addEventListener('DOMContentLoaded', ensureStyle, {{once:true}});
        }} catch(_e) {{}}
      }})();
    """
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": source})
    except Exception:
        pass
