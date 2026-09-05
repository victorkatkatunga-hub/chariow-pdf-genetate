import os
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, EmailStr
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Initialisation de FastAPI
app = FastAPI(
    title="Chariow PDF E-Book Generator",
    description="Service backend pour générer des e-books PDF via l'IA et les envoyer par e-mail.",
    version="1.0.0"
)

# Configuration du client Google GenAI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Modèle de données pour la requête
class EBookRequest(BaseModel):
    topic: str
    recipient_email: EmailStr

# --- FONCTION 1 : Génération du contenu via Gemini ---
def generate_ebook_text(topic: str) -> str:
    if not ai_client:
        raise ValueError("GEMINI_API_KEY non configurée dans les variables d'environnement.")
    
    prompt = f"""
    Rédige un e-book complet, synthétique, bien structuré et captivant sur le sujet suivant : '{topic}'.
    Inclus une introduction percutante, 3 chapitres détaillés et une conclusion pratique.
    Le ton doit être professionnel, clair et engageant pour un guide numérique.
    """
    
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text

# --- FONCTION 2 : Création du PDF avec ReportLab ---
def build_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'EbookTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor='#1A202C',
        spaceAfter=20
    )
    body_style = ParagraphStyle(
        'EbookBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor='#2D3748',
        spaceAfter=10
    )
    
    story = []
    lines = text.split('\n')
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            story.append(Spacer(1, 8))
            continue
        
        # Détection basique des titres
        if line_str.startswith('#') or line_str.isupper() and len(line_str) < 50:
            clean_title = line_str.lstrip('#').strip()
            story.append(Paragraph(clean_title, title_style))
        else:
            story.append(Paragraph(line_str, body_style))
            
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- FONCTION 3 : Envoi par e-mail SMTP ---
def send_email_with_pdf(recipient_email: str, pdf_bytes: bytes, topic: str):
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_email or not smtp_password:
        raise ValueError("Configuration SMTP manquante (SMTP_EMAIL ou SMTP_PASSWORD).")
        
    msg = MIMEMultipart()
    msg['From'] = smtp_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Votre E-Book gratuit : {topic}"
    
    body = f"Bonjour,\n\nVeuillez trouver ci-joint votre e-book personnalisé sur '{topic}'.\n\nBonne lecture !"
    msg.attach(MIMEText(body, 'plain'))
    
    # Attachement du fichier PDF
    filename = f"ebook_{topic.replace(' ', '_').lower()[:20]}.pdf"
    part = MIMEApplication(pdf_bytes, Name=filename)
    part['Content-Disposition'] = f'attachment; filename="{filename}"'
    msg.attach(part)
    
    # Connexion au serveur SMTP Gmail
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)

# --- TÂCHE EN ARRIÈRE-PLAN ---
def process_ebook_generation(topic: str, recipient_email: str):
    try:
        text = generate_ebook_text(topic)
        pdf_bytes = build_pdf(text)
        send_email_with_pdf(recipient_email, pdf_bytes, topic)
        print(f"[SUCCÈS] E-book sur '{topic}' envoyé avec succès à {recipient_email}")
    except Exception as e:
        print(f"[ERREUR] Échec du traitement : {e}")

# --- ENDPOINTS ---
@app.get("/", tags=["Home"])
def read_root():
    return {
        "service": "Service de Génération d'E-Book d'IA",
        "status": "Live",
        "message": "Prêt à recevoir les requêtes."
    }

@app.post("/generate-ebook", tags=["E-Book Generator"])
def generate_ebook(request: EBookRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_ebook_generation, request.topic, request.recipient_email)
    return {
        "status": "success",
        "message": f"La génération de l'e-book sur '{request.topic}' est lancée. Il sera envoyé à {request.recipient_email} sous peu."
}
