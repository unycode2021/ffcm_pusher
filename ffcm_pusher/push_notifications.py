import frappe
import requests
import json
from frappe import enqueue
import firebase_admin
import re
from firebase_admin import credentials
from firebase_admin import messaging

frappe.utils.logger.set_log_level("DEBUG")
fcm_log = frappe.logger("ffcm_pusher", allow_site=False, file_count=10)

def initialize_firebase_pusher():
    ffcm_settings = frappe.get_doc("FFCM Settings")
    if not ffcm_settings.google_auth_file:
        frappe.throw("Google Auth File is not set")

    init_fcm(
        ffcm_settings.project_id,
        os.path.join(frappe.get_site_path(), ffcm_settings.google_auth_file),
    )


def init_fcm(project_id, cred_path):
    # Initialize Firebase Admin SDK if not already initialized
    if not firebase_admin._apps:
       fcm_log.debug("Initializing Firebase Admin.")
       try:
              cred = credentials.Certificate(cred_path)  
              app = firebase_admin.initialize_app(cred, {"projectId": project_id})
       except Exception as e:
              fcm_log.debug("Error initializing Firebase Admin: {}".format(e))
        
    return app

def user_id(doc):
    user_email = doc.for_user
    device = frappe.get_all(
        "FFCM Device", filters={"user": user_email}, fields=["device_token"]
    )
    return device


@frappe.whitelist()
def send_push_notification(doc, event):
    devices = user_id(doc)
    for device in devices:
        enqueue(
            process_notification,
            queue="default",
            now=False,
            token=device.device_token,
            subject=doc.subject,
            message=doc.message,
        )


def convert_message(message):
    CLEANR = re.compile("<.*?>")
    cleanmessage = re.sub(CLEANR, "", message)
    return cleanmessage


@frappe.whitelist()
def process_notification(token, subject, message):
    body = convert_message(message)
    title = convert_message(subject)
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body), token=token
    )

    try:
        response = messaging.send(message)
        frappe.msgprint(f"Successfully sent message: {response}")
        frappe.log_error(f"Successfully sent message: {response}")

    except Exception as e:
        frappe.log_error(f"Failed to send notification: {e}")
        frappe.throw("Notification failed")
