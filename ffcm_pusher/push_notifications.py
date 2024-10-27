import re
import os
import json
import frappe
from frappe import enqueue
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging

frappe.utils.logger.set_log_level("DEBUG")
fcm_log = frappe.logger("ffcm_pusher", allow_site=False, file_count=10)

def initialize_firebase_pusher(doc, event, silent=False):
    ffcm_settings = frappe.get_doc("FFCM Settings")
    if not ffcm_settings.google_auth_file:
        frappe.throw("Google Auth File is not set")

    # cred_path = os.path.join(frappe.get_site_path(), ffcm_settings.google_auth_file)
    site_path = os.path.abspath(frappe.get_site_path())
    cred_path = os.path.join(site_path, ffcm_settings.google_auth_file[1:])

    app = init_fcm(
        ffcm_settings.project_id,
        cred_path
    )
    
    if not silent:
        if not app:
            frappe.throw("Firebase-admin SDK App not initialized.")
        frappe.msgprint("Firebase-admin SDK App initialized. You can now send push notifications.")
    return app


def init_fcm(project_id, cred_path):
    app = None
    # Initialize Firebase Admin SDK if not already initialized
    if not firebase_admin._apps:
        fcm_log.debug("Initializing Firebase Admin.")
        try:
            cred = credentials.Certificate(cred_path)
            app = firebase_admin.initialize_app(cred, {"projectId": project_id})
        except Exception as e:
            fcm_log.debug("Error initializing Firebase Admin: {}".format(e))
            frappe.throw("Error initializing Firebase Admin: {}".format(e))
    return app

def user_id(doc):
    devices = frappe.get_all(
        "FFCM Device", filters={"device_user": doc.for_user}, fields="*"
    )
    return devices


@frappe.whitelist()
def send_push_notification(doc, event):
    devices = user_id(doc)
    for device in devices:
        fcm_log.debug(f"Sending Notifcation for {device.device_user}")
        enqueue(
            process_notification,
            queue="default",
            now=True,
            token=device.device_token,
            doc=doc,
        )


def convert_message(message):
    CLEANR = re.compile("<.*?>")
    cleanmessage = re.sub(CLEANR, "", message)
    return cleanmessage


@frappe.whitelist()
def process_notification(token, doc):
    app = initialize_firebase_pusher(doc, None, True)
    body = ""
    data = doc.data and doc.data["1"] or None
    if doc.message:
        body = convert_message(doc.message)

    title = convert_message(doc.title)
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body), token=token, data=data
    )

    try:
        response = messaging.send(message, dry_run=doc.dry_run)
        frappe.msgprint(f"Successfully sent message: {response}")
    except Exception as e:
        error = frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;")
        frappe.throw(f"Failed to send notification: {error}")
