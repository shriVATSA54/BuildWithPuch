
import os
import smtplib
from email.message import EmailMessage
from typing import Annotated
from pydantic import Field, BaseModel
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp.server.auth.provider import AccessToken

# Load environment variables

from dotenv import load_dotenv
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- Rich Tool Description Model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None

# --- Simple Auth Setup ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="reminder-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Initialize MCP Server ---
TOKEN = "my-secret-token"
mcp = FastMCP("Simple Reminder MCP Server", auth=SimpleBearerAuthProvider(TOKEN))

# --- Start Scheduler ---
scheduler = BackgroundScheduler()
scheduler.start()

# --- Email Tool ---
EmailToolDescription = RichToolDescription(
    description="Sends an email using the provided recipient, subject, and message content.",
    use_when="The user asks to send an email, such as 'send email to example@gmail.com'.",
    side_effects="An email is sent using SMTP from the configured address."
)
@mcp.tool(description="Send an email to someone with a subject and message.")
async def send_email(
    to: Annotated[str, Field(description="Recipient email address")],
    subject: Annotated[str, Field(description="Email subject")],
    content: Annotated[str, Field(description="Email body content")]
) -> str:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "❌ Email credentials are not set in environment variables."

    try:
        
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to
        msg.set_content(content)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            print("🔐 Connected to SMTP server.")
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            print("✅ Logged in.")
            smtp.send_message(msg)
            print("✅ Email sent successfully!")

        return f"✅ Email sent to {to} with subject: '{subject}'"
    except Exception as e:
        print("❌ Error sending email:", str(e))
        return f"❌ Failed to send email: {str(e)}"

# --- Reminder Tool ---
ReminderToolDescription = RichToolDescription(
    description="Sets a reminder to notify you after a certain number of minutes.",
    use_when="User says something like 'Remind me to drink water in 10 minutes'.",
    side_effects="Sends a reminder message after the specified delay."
)

@mcp.tool(description=ReminderToolDescription.model_dump_json())
async def remind(
    message: Annotated[str, Field(description="What to remind you about.")],
    after_minutes: Annotated[int, Field(description="How many minutes from now to remind you.")]
) -> str:
    def send_reminder():
        print(f"[REMINDER] ⏰: {message}")
        with open("reminder_log.txt", "a") as f:
            f.write(f"[{datetime.now()}] Reminder: {message}\n")

    run_time = datetime.now() + timedelta(minutes=after_minutes)
    scheduler.add_job(send_reminder, trigger='date', run_date=run_time)
    return f"⏰ Reminder set: '{message}' in {after_minutes} minute(s)."

# --- In-Memory ToDo Storage ---
todo_list = []

# --- ToDo Add Tool ---
TodoToolDescription = RichToolDescription(
    description="Adds a task to your to-do list.",
    use_when="When the user says 'todo make report' or 'todo clean room'.",
    side_effects="Stores the task in a temporary in-memory list."
)

@mcp.tool(description=TodoToolDescription.model_dump_json())
async def todo(
    task: Annotated[str, Field(description="The task to add to your to-do list.")]
) -> str:
    todo_list.append(task)
    return f"Added to your to-do list: '{task}'"

# --- ToDo View Tool ---
MyTodoToolDescription = RichToolDescription(
    description="Displays your current to-do list.",
    use_when="User wants to check tasks — e.g., 'mytodo'.",
    side_effects="None."
)

@mcp.tool(description=MyTodoToolDescription.model_dump_json())
async def mytodo() -> str:
    if not todo_list:
        return "✅ Your to-do list is empty."
    return "📝 Your to-do list:\n" + "\n".join([f"- {t}" for t in todo_list])

# --- ToDo Complete Tool ---
CompleteTodoToolDescription = RichToolDescription(
    description="Marks a to-do task as complete and removes it.",
    use_when="User says 'complete homework' or 'mark shopping done'.",
    side_effects="Removes the task."
)

@mcp.tool(description=CompleteTodoToolDescription.model_dump_json())
async def complete(
    task_keyword: Annotated[str, Field(description="A keyword from the task to mark as completed.")]
) -> str:
    for t in todo_list:
        if task_keyword.lower() in t.lower():
            todo_list.remove(t)
            return f"✅ Task '{t}' marked as complete and removed."
    return f"❌ No matching task found for: '{task_keyword}'"

# --- Validation Tool ---
@mcp.tool
def validate() -> str:
    #Add phone number with countrycode   ex if country code is +91 and number 9999999999 then return "919999999999"
    return ""

# --- Main Entry ---
async def main():
    print("✅ MCP Server running at http://0.0.0.0:8085")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8085)

if __name__ == "__main__":
    asyncio.run(main())
