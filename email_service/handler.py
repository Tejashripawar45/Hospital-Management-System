import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_env():
    """
    Manually parse .env files from the current directory or parent directory
    to avoid needing external dependencies like python-dotenv.
    """
    for filepath in ['.env', '../.env']:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        parts = line.split('=', 1)
                        key = parts[0].strip()
                        val = parts[1].strip()
                        # Remove quotes if present
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        if val.startswith("'") and val.endswith("'"):
                            val = val[1:-1]
                        os.environ.setdefault(key, val)

# Load env variables immediately on startup
load_env()

def send_email(event, context):
    try:
        # Determine request payload
        body_str = event.get('body', '{}')
        if isinstance(body_str, str):
            try:
                body = json.loads(body_str)
            except Exception:
                body = {}
        else:
            body = body_str

        trigger_type = body.get('trigger_type')
        recipient = body.get('recipient')
        data = body.get('data', {})

        if not trigger_type or not recipient:
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": "Missing trigger_type or recipient"})
            }

        # Formulate email subject and body
        subject = ""
        html_content = ""
        text_content = ""

        if trigger_type == 'SIGNUP_WELCOME':
            username = data.get('username', 'User')
            role = data.get('role', 'User')
            full_name = data.get('full_name', username)
            
            subject = "Welcome to HMS Portal!"
            text_content = f"Hello {full_name},\n\nWelcome to the Hospital Management System! You have registered as a {role}.\n\nBest regards,\nThe HMS Team"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #f3f4f6; padding: 20px;">
                <div style="background-color: white; padding: 30px; border-radius: 8px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #4f46e5; margin-bottom: 20px;">Welcome to HMS Portal!</h2>
                    <p>Hello <strong>{full_name}</strong>,</p>
                    <p>Thank you for registering. Your account has been successfully created with the following details:</p>
                    <table style="width: 100%; margin: 20px 0; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold; color: #4b5563;">Username:</td>
                            <td style="padding: 8px 0; color: #1f2937;">{username}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold; color: #4b5563;">Role:</td>
                            <td style="padding: 8px 0; color: #1f2937; text-transform: capitalize;">{role}</td>
                        </tr>
                    </table>
                    <p style="margin-top: 30px;">Log in to the system at any time to manage your availability slots or book appointments.</p>
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #9ca3af;">This is an automated notification from the local HMS service.</p>
                </div>
            </body>
            </html>
            """
            
        elif trigger_type == 'BOOKING_CONFIRMATION':
            booking_id = data.get('booking_id', 'N/A')
            patient_name = data.get('patient_name', 'Patient')
            doctor_name = data.get('doctor_name', 'Doctor')
            date_str = data.get('date', '')
            time_slot = data.get('time_slot', '')
            doctor_email = data.get('doctor_email', '')
            
            subject = f"Appointment Confirmed with Dr. {doctor_name}"
            text_content = f"Hello {patient_name},\n\nYour appointment (Booking ID: {booking_id}) with Dr. {doctor_name} has been confirmed.\nDate: {date_str}\nTime: {time_slot}\n\nBest regards,\nThe HMS Team"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #f3f4f6; padding: 20px;">
                <div style="background-color: white; padding: 30px; border-radius: 8px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #10b981; margin-bottom: 20px;">Appointment Booking Confirmed!</h2>
                    <p>Hello <strong>{patient_name}</strong>,</p>
                    <p>Your appointment has been successfully booked and confirmed. Details below:</p>
                    <div style="background-color: #f9fafb; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>Doctor:</strong> Dr. {doctor_name} ({doctor_email})</p>
                        <p style="margin: 5px 0;"><strong>Date:</strong> {date_str}</p>
                        <p style="margin: 5px 0;"><strong>Time Slot:</strong> {time_slot}</p>
                        <p style="margin: 5px 0; font-size: 13px; color: #6b7280;"><strong>Booking ID:</strong> #{booking_id}</p>
                    </div>
                    <p style="margin-top: 30px;">If this appointment has been linked to your Google Calendar, it will also appear there automatically.</p>
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #9ca3af;">This is an automated notification from the local HMS service.</p>
                </div>
            </body>
            </html>
            """
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": f"Unsupported trigger type: {trigger_type}"})
            }

        # Terminal output logger (mock representation)
        print("\n" + "=" * 50)
        print(f"=== [LOCAL HMS SERVERLESS EMAIL NOTIFICATION] ===")
        print(f"Recipient: {recipient}")
        print(f"Subject:   {subject}")
        print(f"Trigger:   {trigger_type}")
        print("-" * 50)
        print(text_content)
        print("=" * 50 + "\n")

        # Check SMTP configs to attempt real sending
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = os.getenv('SMTP_PORT', '587')
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASSWORD')

        email_sent_real = False
        message_detail = "Email output printed to console."

        if smtp_user and smtp_pass and 'your_email' not in smtp_user:
            try:
                # Build MIME mail
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = smtp_user
                msg['To'] = recipient

                part1 = MIMEText(text_content, 'plain')
                part2 = MIMEText(html_content, 'html')
                msg.attach(part1)
                msg.attach(part2)

                # Connect and send
                server = smtplib.SMTP(smtp_host, int(smtp_port))
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, recipient, msg.as_string())
                server.quit()
                
                email_sent_real = True
                message_detail = "Real email sent via SMTP successfully."
                print(f"[SMTP] Successfully sent real email to {recipient}")
            except Exception as smtp_err:
                print(f"[SMTP ERROR] Failed to send real email: {smtp_err}")
                message_detail = f"Mocked (SMTP failed: {smtp_err})"

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "real_email_sent": email_sent_real,
                "message": message_detail
            })
        }

    except Exception as e:
        print(f"[HANDLER ERROR] Exception: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }
