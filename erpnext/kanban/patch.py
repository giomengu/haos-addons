#!/usr/bin/env python3
"""Install the ALD Kanban component into the checked-out Frappe Studio frontend."""
from pathlib import Path

root = Path("/home/frappe/frappe-bench/apps/studio/frontend")

def inject(path, needle, insertion, marker):
    file = root / path
    text = file.read_text()
    if marker in text:
        print(f"Already patched: {path}")
        return
    if text.count(needle) != 1:
        raise RuntimeError(f"Expected exactly one anchor in {path}: {needle!r}")
    file.write_text(text.replace(needle, insertion + needle, 1))
    print(f"Patched: {path}")

inject("src/json_types/index.ts",
       'export { default as TextBlock } from "./studio/TextBlock.json"',
       'export { default as Kanban } from "./studio/Kanban.json"\n',
       'export { default as Kanban }')
inject("src/utils/constants.js",
       'export const STUDIO_COMPONENTS = ',
       '',
       '__never__') if False else None

constants = root / "src/utils/constants.js"
data = constants.read_text()
if '"Kanban"' not in data:
    import re
    replacement, count = re.subn(
        r'(export const STUDIO_COMPONENTS\s*=\s*\[[^\]]*)(\])',
        lambda m: m.group(1) + ', "Kanban"' + m.group(2), data, count=1)
    if count != 1:
        raise RuntimeError("Cannot locate STUDIO_COMPONENTS registry")
    constants.write_text(replacement)

inject("src/globals.ts",
       'export function registerGlobalComponents(app: App) {',
       '',
       '__never__') if False else None
globals_path = root / "src/globals.ts"
g = globals_path.read_text()
if 'import Kanban from "@/components/AppLayout/Kanban.vue"' not in g:
    anchor = 'import TextBlock from "@/components/AppLayout/TextBlock.vue"'
    if anchor not in g: raise RuntimeError("Studio global import anchor missing")
    g = g.replace(anchor, anchor + '\nimport Kanban from "@/components/AppLayout/Kanban.vue"', 1)
if 'app.component("Kanban", Kanban)' not in g:
    anchor = 'app.component("TextBlock", TextBlock)'
    if anchor not in g: raise RuntimeError("Studio global registration anchor missing")
    g = g.replace(anchor, anchor + '\n\tapp.component("Kanban", Kanban)', 1)
globals_path.write_text(g)

components = root / "src/data/components.ts"
c = components.read_text()
if 'Kanban: { name: "Kanban"' not in c:
    anchor = 'export const COMPONENTS: FrappeUIComponents = {'
    if anchor not in c: raise RuntimeError("Studio component catalog anchor missing")
    c = c.replace(anchor, anchor + '\n\tKanban: { name: "Kanban", title: "Kanban", icon: LucideColumns3, initialState: { doctype: "", statusField: "status", titleField: "name", columns: "Open,Working,Completed", limit: 100 } },', 1)
components.write_text(c)
print("ALD Kanban registrations installed.")
