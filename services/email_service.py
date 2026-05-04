"""
services/email_service.py
Email notification service for Project PA.

Sends discipline-aware notifications via Gmail SMTP (Flask-Mail).
Triggered by the nightly scheduler or specific user events.

Environment variables required:
    MAIL_USERNAME  — Gmail address (e.g. deeppatel26075@gmail.com)
    MAIL_PASSWORD  — Gmail App Password (NOT your account password)
                     Generate at: https://myaccount.google.com/apppasswords

Note: Gmail requires 2-Step Verification to be enabled before generating
      App Passwords.
"""
import logging
from flask import current_app
from flask_mail import Message

logger = logging.getLogger(__name__)


def _mail():
    """Lazy import of mail extension to avoid circular imports."""
    from app import mail
    return mail


def send_streak_at_risk(user_email: str, user_name: str, streak: int,
                        unfinished_count: int) -> bool:
    """
    Alert sent in the evening when a user still has unfinished High-priority tasks.
    Only sent if the user has email_notifications enabled.

    Returns True if sent successfully, False otherwise.
    """
    try:
        msg = Message(
            subject=f"⚠️ Your {streak}-day streak is at risk, {user_name}!",
            recipients=[user_email],
            html=f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f1a; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #1a1a2e; border-radius: 16px;
                  border: 1px solid rgba(139,92,246,0.3); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #7c3aed, #db2777); padding: 32px;
               text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 24px; }}
    .header p {{ color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px; }}
    .body {{ padding: 32px; color: #e2e8f0; }}
    .streak-box {{ background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.4);
                   border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }}
    .streak-num {{ font-size: 48px; font-weight: 900; color: #a78bfa; }}
    .streak-label {{ color: #94a3b8; font-size: 14px; margin-top: 4px; }}
    .warning {{ background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
                border-radius: 8px; padding: 16px; color: #fca5a5; font-size: 14px; margin: 16px 0; }}
    .cta {{ display: block; background: linear-gradient(135deg, #7c3aed, #db2777); color: #fff;
            text-decoration: none; padding: 14px 28px; border-radius: 8px; text-align: center;
            font-weight: 700; margin: 24px 0; font-size: 16px; }}
    .footer {{ text-align: center; color: #475569; font-size: 12px; padding: 16px 32px 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⚡ Project PA Alert</h1>
      <p>Discipline Intelligence System</p>
    </div>
    <div class="body">
      <p>Hey <strong>{user_name}</strong>,</p>
      <p>You have <strong>{unfinished_count} unfinished High-priority task(s)</strong> today.
         Your streak is on the line!</p>
      <div class="streak-box">
        <div class="streak-num">🔥 {streak}</div>
        <div class="streak-label">Day Streak — Don't break it now</div>
      </div>
      <div class="warning">
        ⚠️ If you don't complete your High-priority tasks today, your streak will reset to 0.
      </div>
      <p>Finish strong. Every day you show up counts.</p>
      <a class="cta" href="http://127.0.0.1:5000/dashboard">Open Dashboard →</a>
    </div>
    <div class="footer">
      Project PA · Discipline Intelligence System<br>
      <small>Manage notifications in your <a href="http://127.0.0.1:5000/profile" style="color:#7c3aed;">Profile Settings</a></small>
    </div>
  </div>
</body>
</html>
""",
        )
        _mail().send(msg)
        logger.info("Streak-at-risk email sent to %s", user_email)
        return True
    except Exception as exc:
        logger.error("Failed to send streak-at-risk email to %s: %s", user_email, exc)
        return False


def send_streak_broken(user_email: str, user_name: str, lost_streak: int) -> bool:
    """Alert when a streak resets to 0."""
    try:
        msg = Message(
            subject=f"💔 Streak reset — Time to rebuild, {user_name}",
            recipients=[user_email],
            html=f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f1a; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #1a1a2e; border-radius: 16px;
                  border: 1px solid rgba(239,68,68,0.3); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #991b1b, #7c2d12); padding: 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 24px; }}
    .body {{ padding: 32px; color: #e2e8f0; }}
    .stat {{ background: rgba(239,68,68,0.1); border-radius: 8px; padding: 16px;
             text-align: center; margin: 16px 0; }}
    .stat-num {{ font-size: 40px; font-weight: 900; color: #f87171; }}
    .cta {{ display: block; background: linear-gradient(135deg, #7c3aed, #db2777); color: #fff;
            text-decoration: none; padding: 14px 28px; border-radius: 8px; text-align: center;
            font-weight: 700; margin: 24px 0; }}
    .footer {{ text-align: center; color: #475569; font-size: 12px; padding: 16px 32px 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>💔 Streak Broken</h1></div>
    <div class="body">
      <p>Hey <strong>{user_name}</strong>,</p>
      <p>Your streak was broken. But every master was once a beginner.</p>
      <div class="stat">
        <div class="stat-num">{lost_streak} days</div>
        <p style="color:#94a3b8; margin:4px 0 0;">Lost — But not forgotten</p>
      </div>
      <p>Start fresh today. The comeback is always stronger than the setback.</p>
      <a class="cta" href="http://127.0.0.1:5000/dashboard">Start Day 1 Again →</a>
    </div>
    <div class="footer">
      Project PA · Discipline Intelligence System<br>
      <small><a href="http://127.0.0.1:5000/profile" style="color:#7c3aed;">Manage notifications</a></small>
    </div>
  </div>
</body>
</html>
""",
        )
        _mail().send(msg)
        logger.info("Streak-broken email sent to %s", user_email)
        return True
    except Exception as exc:
        logger.error("Failed to send streak-broken email to %s: %s", user_email, exc)
        return False


def send_personal_best(user_email: str, user_name: str, score: float,
                       previous_best: float) -> bool:
    """Celebrate when a user achieves a new personal best score."""
    try:
        msg = Message(
            subject=f"🏆 New Personal Best! You scored {score:.0f} pts today!",
            recipients=[user_email],
            html=f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f1a; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #1a1a2e; border-radius: 16px;
                  border: 1px solid rgba(251,191,36,0.3); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #b45309, #92400e); padding: 32px; text-align: center; }}
    .header h1 {{ color: #fde68a; margin: 0; font-size: 24px; }}
    .body {{ padding: 32px; color: #e2e8f0; }}
    .score-box {{ display: flex; gap: 16px; margin: 20px 0; }}
    .score-card {{ flex: 1; background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3);
                   border-radius: 12px; padding: 16px; text-align: center; }}
    .score-num {{ font-size: 36px; font-weight: 900; }}
    .score-label {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
    .new {{ color: #fbbf24; }}
    .old {{ color: #64748b; }}
    .cta {{ display: block; background: linear-gradient(135deg, #b45309, #7c3aed); color: #fff;
            text-decoration: none; padding: 14px 28px; border-radius: 8px; text-align: center;
            font-weight: 700; margin: 24px 0; }}
    .footer {{ text-align: center; color: #475569; font-size: 12px; padding: 16px 32px 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>🏆 Personal Best Achieved!</h1></div>
    <div class="body">
      <p>Outstanding work, <strong>{user_name}</strong>! You just set a new personal best.</p>
      <div class="score-box">
        <div class="score-card">
          <div class="score-num new">🏆 {score:.0f}</div>
          <div class="score-label">Today's Score (NEW BEST)</div>
        </div>
        <div class="score-card">
          <div class="score-num old">{previous_best:.0f}</div>
          <div class="score-label">Previous Best</div>
        </div>
      </div>
      <p>This is what elite discipline looks like. Keep it up!</p>
      <a class="cta" href="http://127.0.0.1:5000/analytics">See Your Analytics →</a>
    </div>
    <div class="footer">
      Project PA · Discipline Intelligence System<br>
      <small><a href="http://127.0.0.1:5000/profile" style="color:#7c3aed;">Manage notifications</a></small>
    </div>
  </div>
</body>
</html>
""",
        )
        _mail().send(msg)
        logger.info("Personal-best email sent to %s", user_email)
        return True
    except Exception as exc:
        logger.error("Failed to send personal-best email to %s: %s", user_email, exc)
        return False
