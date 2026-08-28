import os
import fitz

from sentence_transformers import SentenceTransformer, util
import torch

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.db.models import Q

from googletrans import Translator
from gtts import gTTS

from .models import Document


def home(request):
    return render(request, "register.html")


from django.contrib import messages

def register_view(request):

    # ✅ Prevent access if already logged in
    def register_view(request):

      if request.user.is_authenticated:
        return redirect("dashboard")  # keep this

      if request.method == "POST":
        ...
    
      return render(request, "register.html")

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists!")
            return render(request, "register.html")

        User.objects.create_user(username=username, email=email, password=password)

        return redirect("login")

    return render(request, "register.html")

@login_required
def documents_view(request):
    documents = Document.objects.filter(user=request.user).order_by('-id')

    return render(request, "documents.html", {
        "documents": documents
    })


@login_required
def audio_view(request):
    documents = Document.objects.filter(user=request.user).order_by('-id')

    audio_list = []

    for doc in documents:
        audio_list.append({
            "title": doc.title,
            "english_audio": f"/media/audio/{doc.id}_en.mp3",
            "translated_audio": f"/media/audio/{doc.id}_tr.mp3"
        })

    return render(request, "audio.html", {
        "audio_list": audio_list
    })


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

def login_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        print("USERNAME:", username)
        print("PASSWORD:", password)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            print("LOGIN SUCCESS")

            return redirect("/dashboard/")   # ✅ FORCE URL

        else:
            print("LOGIN FAILED")
            messages.error(request, "Invalid username or password")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    documents = Document.objects.filter(user=request.user).order_by('-id')

    total_documents = documents.count()
    total_summaries = documents.exclude(summary="").exclude(summary__isnull=True).count()
    latest_documents = documents[:5]

    context = {
        "documents": documents,
        "total_documents": total_documents,
        "total_summaries": total_summaries,
        "latest_documents": latest_documents,
    }

    return render(request, "dashboard.html", context)


import fitz  # PyMuPDF

def extract_text_from_pdf(file_path):

    text = ""

    doc = fitz.open(file_path)

    for page in doc:
        text += page.get_text()

    doc.close()

    return text


from transformers import pipeline

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def chunk_text(text, chunk_size=1000):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def generate_summary(text):

    if not text or len(text.strip()) == 0:
        return "No content available for summarization."

    text = text.strip().replace("\n", " ")

    chunks = chunk_text(text, chunk_size=400)
    total_words = len(text.split())

    # ✅ dynamic length calculation
    if total_words < 300:
        max_len = 80
        min_len = 30
    elif total_words < 1000:
        max_len = 150
        min_len = 50
    else:
        max_len = 250
        min_len = 80

    summaries = []

    try:
        for chunk in chunks[:8]:
            result = summarizer(
                chunk,
                max_length=max_len,   # ✅ dynamic
                min_length=min_len,   # ✅ dynamic
                do_sample=False
            )
            summaries.append(result[0]["summary_text"])

        final_text = " ".join(summaries)

        # final summary also dynamic
        final_summary = summarizer(
            final_text,
            max_length=max_len + 50,
            min_length=min_len,
            do_sample=False
        )

        return final_summary[0]["summary_text"]

    except Exception as e:
        print("Summarization error:", e)
        return "Summary could not be generated."


from sentence_transformers import SentenceTransformer, util
import torch
import re

recommendation_model = SentenceTransformer('all-MiniLM-L6-v2')


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_recommendations(current_document, top_k=5, min_score=0.35):
    all_docs = Document.objects.exclude(id=current_document.id)

    if not all_docs.exists():
        return []

    current_text = clean_text(current_document.summary or current_document.extracted_text)

    if not current_text:
        return []

    doc_list = []
    doc_texts = []

    for doc in all_docs:
        compare_text = clean_text(doc.summary or doc.extracted_text)
        if compare_text:
            doc_list.append(doc)
            doc_texts.append(compare_text)

    if not doc_texts:
        return []

    current_embedding = recommendation_model.encode(current_text, convert_to_tensor=True)
    doc_embeddings = recommendation_model.encode(doc_texts, convert_to_tensor=True)

    cosine_scores = util.cos_sim(current_embedding, doc_embeddings)[0]

    top_results = torch.topk(cosine_scores, k=min(top_k * 2, len(doc_list)))

    recommendations = []
    seen_titles = set()

    for idx, score in zip(top_results.indices.tolist(), top_results.values.tolist()):
        doc = doc_list[idx]

        if score < min_score:
            continue

        normalized_title = doc.title.strip().lower()
        if normalized_title in seen_titles:
            continue

        doc.similarity_score = round(float(score) * 100, 2)
        recommendations.append(doc)
        seen_titles.add(normalized_title)

        if len(recommendations) >= top_k:
            break

    return recommendations

@login_required
def upload_document(request):

    if request.method == "POST":

        import os
        import re
        from django.conf import settings
        from gtts import gTTS
        from googletrans import Translator
        title = request.POST.get("title")
        file = request.FILES.get("file")
        language = request.POST.get("language")

        document = Document.objects.create(
            user=request.user,
            title=title,
            file=file
        )

        file_path = document.file.path

        # ✅ TEXT EXTRACTION
        extracted_text = extract_text_from_pdf(file_path)
        document.extracted_text = extracted_text

        # ✅ SUMMARY (slightly increased)
        summary = generate_summary(extracted_text[:5000])
        document.summary = summary

        document.save()

        # ✅ CREATE AUDIO FOLDER
        audio_folder = os.path.join(settings.MEDIA_ROOT, "audio")
        os.makedirs(audio_folder, exist_ok=True)

        # ✅ FILE PATHS
        english_audio_path = os.path.join(audio_folder, f"{document.id}_en.mp3")
        translated_audio_path = os.path.join(audio_folder, f"{document.id}_tr.mp3")

        # =========================
        # ✅ ENGLISH AUDIO FIX
        # =========================
        clean_en = re.sub(r'[^a-zA-Z0-9.,!? ]', '', extracted_text)
        safe_en = clean_en[:800]

        if len(safe_en.strip()) == 0:
            safe_en = "Audio not available"

        try:
            tts = gTTS(safe_en, lang="en")
            tts.save(english_audio_path)
        except Exception as e:
            print("ENGLISH TTS ERROR:", e)

        # =========================
        # ✅ TRANSLATE FULL DOCUMENT
        translator = Translator()

        full_text = extracted_text[:10000]

        translated = translator.translate(
            full_text,
            dest=language
        )

        translated_text = translated.text

        # ✅ SAVE FULL TRANSLATED AUDIO
        tts2 = gTTS(
            translated_text,
            lang=language,
            slow=False
        )

        tts2.save(translated_audio_path)

        # ✅ URLs
        english_audio_url = f"/media/audio/{document.id}_en.mp3"
        translated_audio_url = f"/media/audio/{document.id}_tr.mp3"

        context = {
            "document": document,
            "summary": summary,
            "translated_text": translated_text,
            "english_audio_url": english_audio_url,
            "translated_audio_url": translated_audio_url,
        }

        return render(request, "result.html", context)

    return render(request, "upload.html")

import uuid

def translate_text(request):

    text = request.GET.get("text")
    lang = request.GET.get("lang")

    if not text or not lang:
        return JsonResponse({"error": "Missing text or language"}, status=400)

    translator = Translator()

    translated = translator.translate(text, dest=lang)

    translated_text = translated.text

    audio_folder = os.path.join(settings.MEDIA_ROOT, "audio")
    os.makedirs(audio_folder, exist_ok=True)

    # unique filename to avoid caching
    filename = f"translated_{uuid.uuid4().hex}.mp3"

    audio_path = os.path.join(audio_folder, filename)

    tts = gTTS(translated_text, lang=lang)
    tts.save(audio_path)

    audio_url = f"/media/audio/{filename}"

    return JsonResponse({
        "translated_text": translated_text,
        "audio_url": audio_url
    })

import threading

def process_document(document, summary, language):

    from googletrans import Translator
    from gtts import gTTS
    import os
    from django.conf import settings

    try:
        translator = Translator()
        translated = translator.translate(summary, dest=language)
        translated_text = translated.text

        audio_folder = os.path.join(settings.MEDIA_ROOT, "audio")
        os.makedirs(audio_folder, exist_ok=True)

        # English audio
        gTTS(summary[:1000], lang="en").save(
            os.path.join(audio_folder, f"{document.id}_en.mp3")
        )

        # Translated audio
        gTTS(translated_text[:1000], lang=language).save(
            os.path.join(audio_folder, f"{document.id}_tr.mp3")
        )

    except Exception as e:
        print("ERROR:", e)


@login_required
def search_documents(request):

    query = request.GET.get("q")

    documents = []

    if query:

        documents = Document.objects.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(extracted_text__icontains=query)
        )

    context = {
        "query":query,
        "documents":documents
    }

    return render(request,"search_results.html",context)


@login_required
def download_summary(request,doc_id):

    document = Document.objects.get(id=doc_id)

    summary_text = document.summary if document.summary else "No summary available"

    response = HttpResponse(summary_text,content_type="text/plain")

    response["Content-Disposition"] = f'attachment; filename="{document.title}_summary.txt"'

    return response