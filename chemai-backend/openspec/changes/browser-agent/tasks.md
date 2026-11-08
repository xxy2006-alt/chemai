## 1. Browser Tools Implementation

- [x] 1.1 Create `agent/browser_tools.py` with module-level `_browser_lock`, `_browser_instance`, `_page_instance`, `_last_used`
- [x] 1.2 Implement `_get_page()` — lazy init with asyncio.Lock + idle timeout cleanup
- [x] 1.3 Implement `browse_navigate(url, wait_until)` — returns {title, url, text}
- [x] 1.4 Implement `browse_read(selector)` — returns {selector, text} (truncated 8000 chars)
- [x] 1.5 Implement `browse_click(selector)` — returns {selector, before_url, after_url, title}
- [x] 1.6 Implement `browse_input(selector, text)` — returns {selector, text, done}
- [x] 1.7 Implement `browse_screenshot(selector)` — returns {screenshot (base64 PNG), type}
- [x] 1.8 Implement `_cleanup()` — close page + browser

## 2. Browser Expert Sub-Agent

- [x] 2.1 Define browser_expert system prompt — describes tool usage, output JSON contract
- [x] 2.2 Build browser_expert node with `create_sub_agent_node` factory
- [x] 2.3 Register browser_expert in `_agent_node_cache`

## 3. Coordinator Integration

- [x] 3.1 Add `browser_expert` to RoutingDecision agent Literal
- [x] 3.2 Add browser routing rule to coordinator system prompt
- [x] 3.3 Add browser_expert node to graph assembly + conditional edges

## 4. Dependencies

- [x] 4.1 Add `playwright` to `requirements.txt`
- [x] 4.2 Document `playwright install chromium` in deployment notes

## 5. Testing

- [ ] 5.1 Test browse_navigate + browse_read with public URL (needs `playwright install chromium`)
- [ ] 5.2 Test browse_click + browse_input end-to-end (needs chromium)
- [ ] 5.3 Test concurrent access: lock serialization (needs chromium)
- [ ] 5.4 Test idle timeout cleanup (needs chromium)
- [x] 5.5 Test coordinator routes browser intent correctly
