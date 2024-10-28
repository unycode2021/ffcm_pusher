import frappe
from frappe import enqueue


@frappe.whitelist()
def register_device(token):
       user = frappe.get_doc("User", frappe.session.user)
       if frappe.db.exists("FFCM Device",{"device_token":token}):
              return
       
       device = frappe.get_doc({"doctype":"FFCM Device","device_user":user.name,"device_token":token})
       device.insert(ignore_permissions=True)