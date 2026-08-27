import sys, frappe
frappe.init(site="sketch.localhost"); frappe.connect(); frappe.set_user("orch-mcp@example.com")
import os
from sketch import prototype, prototype_files, signature
slug = sys.argv[1]; src = sys.argv[2]
user = "orch-mcp@example.com"
existing = frappe.db.get_value("Sketch Prototype", {"slug": slug, "owner": user}, "name")
if existing: frappe.delete_doc("Sketch Prototype", existing, force=True, ignore_permissions=True)
d = frappe.new_doc("Sketch Prototype")
d.title = slug; d.slug = slug; d.pin = prototype.newest_pin(); d.owner = user
d.insert(ignore_permissions=True)
assert d.owner == user, d.owner; frappe.db.commit()
files = []
for root, _, names in os.walk(src):
    for n in names:
        p = os.path.join(root, n)
        rel = os.path.relpath(p, os.path.dirname(src))
        files.append({"path": rel, "content": open(p, encoding="utf-8").read()})
prototype_files.write_files(d.name, files)
s = signature.mint(d.name, ttl_seconds=600)
print(f"http://127.0.0.1:8007/u/orchmcp/{slug}?theme=light&exp={s['exp']}&sig={s['sig']}")
frappe.destroy()
