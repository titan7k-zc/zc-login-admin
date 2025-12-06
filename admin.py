import customtkinter as ctk
import tkinter.messagebox as messagebox
import threading
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+
import os
from firebase_admin import credentials, firestore, initialize_app

# ==================== CONFIG ====================
SERVICE_ACCOUNT_FILE = "zerocrow22a01-firebase-adminsdk-fbsvc-f4f939aa03.json"
COLLECTION_REQUESTS = "user_requests"
COLLECTION_HTYPE = "htype"  # Fallback collection
LOCAL_TZ = ZoneInfo("Asia/Colombo")  # UTC+5:30

# ==================== INITIALIZE FIREBASE ====================
db = None
firebase_initialized = False
try:
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"File not found: {SERVICE_ACCOUNT_FILE}. Database functions will be disabled.")
    else:
        cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
        initialize_app(cred)
        db = firestore.client()
        firebase_initialized = True
        print("Firebase Admin SDK Initialized Successfully.")
except Exception as e:
    print(f"Firebase Initialization Error: {e}")
    firebase_initialized = False

# ==================== FIRESTORE FUNCTIONS ====================
def get_user_requests():
    if db is None:
        return None
    try:
        docs = db.collection(COLLECTION_REQUESTS).stream()
        requests_list = []
        for doc in docs:
            data = doc.to_dict()
            timestamp = data.get("requested_at")
            if isinstance(timestamp, datetime):
                # Convert UTC to local timezone
                timestamp_local = timestamp.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)
                timestamp_str = timestamp_local.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_str = str(timestamp) if timestamp else "N/A"
            requests_list.append({
                "doc_id": doc.id,
                "email": data.get("email", "N/A"),
                "project": data.get("project", COLLECTION_HTYPE) if isinstance(data.get("project"), str) else COLLECTION_HTYPE,
                "requested_at": timestamp_str
            })
        return requests_list
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None


def approve_request(doc_id):
    if db is None:
        return False
    try:
        request_doc_ref = db.collection(COLLECTION_REQUESTS).document(doc_id)
        request_doc = request_doc_ref.get()
        if not request_doc.exists:
            return False
        request_data = request_doc.to_dict()
        target_collection_name = request_data.get("project")
        if not isinstance(target_collection_name, str) or not target_collection_name:
            target_collection_name = COLLECTION_HTYPE
        
        # Ensure the target collection has the required data, copying all request data
        db.collection(target_collection_name).document(doc_id).set(request_data) 
        
        request_doc_ref.delete()
        return True
    except Exception as e:
        print(f"Approval Error: {e}")
        return False

def reject_request(doc_id):
    if db is None:
        return False
    try:
        db.collection(COLLECTION_REQUESTS).document(doc_id).delete()
        return True
    except Exception as e:
        print(f"Reject Error: {e}")
        return False

# ==================== GUI ====================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class AdminApp(ctk.CTk):
    def __init__(self): # FIX: Changed def init(self) to def __init__(self)
        super().__init__()
        self.title("Firebase Admin Tool")
        self.geometry("1000x800")
        self.resizable(False, False)
        self.selected_requests = {}  # doc_id -> ctk.BooleanVar()
        
        self._setup_requests_frame()
        self._setup_action_buttons()

        self.requests_frame.pack(pady=20, padx=20, fill="both", expand=True)
        self.action_frame.pack(side="bottom", pady=10, fill="x")

        if not firebase_initialized:
            messagebox.showerror("Configuration Error", "Firebase Admin SDK failed to initialize. Check console for details.")
        else:
            self.load_requests()

    def _setup_requests_frame(self):
        self.requests_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.requests_frame, text="Pending User Requests", font=("Helvetica", 20, "bold")).pack(pady=10)
        self.requests_scroll = ctk.CTkScrollableFrame(self.requests_frame, label_text="Awaiting Approval", width=950, height=600)
        self.requests_scroll.pack(pady=0)

    def _setup_action_buttons(self):
        self.action_frame = ctk.CTkFrame(self)
        
        self.refresh_button = ctk.CTkButton(self.action_frame, text="Refresh", width=100, command=self.load_requests)
        self.refresh_button.pack(side="left", padx=20, pady=5)

        self.approve_btn = ctk.CTkButton(self.action_frame, text="Approve Selected", fg_color="#4CAF50", hover_color="#45A049", command=self.confirm_approve_selected)
        self.approve_btn.pack(side="left", padx=20, pady=5)

        self.reject_btn = ctk.CTkButton(self.action_frame, text="Reject Selected", fg_color="#F44336", hover_color="#D32F2F", command=self.confirm_reject_selected)
        self.reject_btn.pack(side="left", padx=20, pady=5)

    def load_requests(self):
        for widget in self.requests_scroll.winfo_children():
            widget.destroy()
        self.selected_requests = {}
        loading_label = ctk.CTkLabel(self.requests_scroll, text="Loading requests...")
        loading_label.pack(pady=20)
        self.refresh_button.configure(state="disabled")

        def load_task():
            data = get_user_requests()
            self.after(0, lambda: self.update_requests_ui(data))

        threading.Thread(target=load_task, daemon=True).start()

    def update_requests_ui(self, requests_data):
        for widget in self.requests_scroll.winfo_children():
            widget.destroy()
        self.refresh_button.configure(state="normal")

        if requests_data is None:
            ctk.CTkLabel(self.requests_scroll, text="Error loading requests. See console.").pack(pady=10)
            return
        if not requests_data:
            ctk.CTkLabel(self.requests_scroll, text="No pending requests.").pack(pady=10)
            return

        for req in requests_data:
            var = ctk.BooleanVar()
            self.selected_requests[req['doc_id']] = var
            frame = ctk.CTkFrame(self.requests_scroll, fg_color=("gray85", "gray17"))
            frame.pack(pady=5, padx=5, fill="x")
            check = ctk.CTkCheckBox(frame, text="", variable=var)
            check.pack(side="left", padx=5, pady=5)
            details_text = (
                f"Email: {req['email']}\n"
                f"Device ID: {req['doc_id']}\n"
                f"Project: {req['project']}\n"
                f"Requested At: {req['requested_at']}"
            )
            ctk.CTkLabel(frame, text=details_text, anchor="w", justify="left").pack(side="left", padx=10, pady=5)

    # ===== BATCH CONFIRMATIONS =====
    def confirm_approve_selected(self):
        selected = [doc_id for doc_id, var in self.selected_requests.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one request to approve.")
            return
        if messagebox.askyesno("Confirm Approval", f"Approve {len(selected)} selected requests?"):
            threading.Thread(target=self.approve_selected_task, args=(selected,), daemon=True).start()

    def confirm_reject_selected(self):
        selected = [doc_id for doc_id, var in self.selected_requests.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one request to reject.")
            return
        if messagebox.askyesno("Confirm Rejection", f"Reject {len(selected)} selected requests?"):
            threading.Thread(target=self.reject_selected_task, args=(selected,), daemon=True).start()

    # ===== BATCH PROCESSING TASKS =====
    def approve_selected_task(self, doc_ids):
        success_count = 0
        for doc_id in doc_ids:
            if approve_request(doc_id):
                success_count += 1
        self.after(0, lambda: messagebox.showinfo("Success", f"Successfully approved {success_count} of {len(doc_ids)} requests."))
        self.after(0, self.load_requests)

    def reject_selected_task(self, doc_ids):
        success_count = 0
        for doc_id in doc_ids:
            if reject_request(doc_id):
                success_count += 1
        self.after(0, lambda: messagebox.showinfo("Success", f"Successfully rejected {success_count} of {len(doc_ids)} requests."))
        self.after(0, self.load_requests)

# ===== MAIN =====
if __name__ == "__main__": # FIX: Changed if name == "main" to if __name__ == "__main__"
    app = AdminApp()
    app.mainloop()