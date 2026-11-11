import datetime
import os
from flask import Flask, render_template, request, session, send_file, abort
from DBConnection import Db
from face_verification import face_verify
from main import main_func
from ppt_summarizer import generate_full_report
from voice_control import main_func2
from air_drawing import main3
from speaker_verification import create_voiceprint, save_voiceprint, voiceprint_path, VOICE_DIR

app= Flask(__name__)
app.secret_key="hi"

img_path=r"C:\Users\Project\PycharmProjects\hand_gestured_based_ppt_controlling\images\\"
slide_path=r"C:\Users\Project\PycharmProjects\hand_gestured_based_ppt_controlling\slides\\"

@app.route("/")
def loginn():
    return render_template("login.html")

@app.route("/login_post", methods=['post'])
def login_post():
    username=request.form['username']
    password=request.form['password']
    db=Db()
    data=db.select("SELECT * FROM USER WHERE email='"+username+"' AND PASSWORD='"+password+"'")
    print(data)
    if len(data)>0:
        data=data[0]
        print(data)
        img=data[3]
        session['uimg']=img
        session['uid']=data[0]
        verified_status = face_verify(img)
        if verified_status == "No face":
            return "<script>alert('No face detected. Please face camera');window.location='/';</script>"
        elif verified_status == "No match":
            return "<script>alert('Unauthorised access detected');window.location='/';</script>"
        else:
            return "<script>alert('Login success');window.location='/user_home';</script>"
    else:
        return "<script>alert('Invalid details');window.location='/';</script>"

@app.route("/logout")
def logout():
    return "<script>window.location='/';</script>"

@app.route("/captured_face")
def captured_face():
    """Image taken by face_verify at the last sign-in (shown in the login page panel).
    'since' (ms) hides an older image left over from a previous sign-in."""
    path = os.path.join(img_path, "a.jpg")
    if not os.path.exists(path):
        abort(404)
    since = request.args.get("since", type=float)
    if since is not None and os.path.getmtime(path) * 1000 < since:
        abort(404)
    response = send_file(path, mimetype="image/jpeg", max_age=0)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/register_post", methods=['post'])
def register_post():
    print(request.form)
    print(request.files)
    name=request.form['name']
    email=request.form['email']
    password=request.form['password']
    image=request.files['image']
    voice=request.files.get('voice')
    dt=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db=Db()
    data=db.select("SELECT * FROM USER WHERE email='"+email+"'")
    if len(data)>0:
        return "<script>alert('Email already used');window.location='/';</script>"
    if voice is None or voice.filename=="":
        return "<script>alert('Please upload a voice recording (mp3 or wav)');window.location='/';</script>"

    # Voice recording -> voiceprint (speaker verification for voice commands)
    os.makedirs(VOICE_DIR, exist_ok=True)
    ext=os.path.splitext(voice.filename)[1].lower() or ".wav"
    voice_file=os.path.join(VOICE_DIR, dt+ext)
    voice.save(voice_file)
    try:
        voiceprint, seconds=create_voiceprint(voice_file)
        print(f"Voiceprint created from {seconds:.1f} s of speech")
    except Exception as e:
        print("Voice enrollment failed:", e)
        os.remove(voice_file)
        msg=" ".join(str(e).replace("'", "").split())
        return "<script>alert('Voice recording not usable: "+msg+"');window.location='/';</script>"

    image.save(img_path+dt+".jpg")
    path="/images/"+dt+".jpg"
    db=Db()
    user_id=db.insert("INSERT INTO USER(NAME, email, image, PASSWORD) VALUES('"+name+"', '"+email+"', '"+path+"', '"+password+"')")
    save_voiceprint(voiceprint, user_id)
    os.replace(voice_file, os.path.join(VOICE_DIR, f"user_{user_id}{ext}"))
    return "<script>alert('Account created');window.location='/';</script>"


def current_voiceprint():
    """Voiceprint of the logged-in user, or None (registered before voice enrollment)."""
    if 'uid' not in session:
        return None
    path=voiceprint_path(session['uid'])
    return path if os.path.exists(path) else None


@app.route("/user_home")
def user_home():
    return render_template("home.html")

@app.route("/upload_ppt")
def upload_ppt():
    return render_template("upload_file.html")

@app.route("/upload_ppt_post", methods=['post'])
def upload_ppt_post():
    slide=request.files['slide']
    dt=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    full_path=slide_path+dt+".jpg"
    slide.save(full_path)
    # img=session['uimg'].split("/")[-1]
    img=os.path.join(img_path, session['uimg'].split("/")[-1])
    aa=main_func(full_path, img, current_voiceprint())
    return "<script>alert('Presentation closed');window.location='/user_home';</script>"



@app.route("/upload_ppt_voice")
def upload_ppt_voice():
    return render_template("upload_file_voice.html")

@app.route("/upload_ppt_voice_post", methods=['post'])
def upload_ppt_voice_post():
    slide=request.files['slide']
    dt=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    full_path=slide_path+dt+".jpg"
    slide.save(full_path)
    aa=main_func2(full_path, current_voiceprint())
    return "<script>alert('Presentation closed');window.location='/user_home';</script>"

@app.route("/file_summarizer")
def file_summarizer():
    return render_template("file_summarizer.html")

@app.route("/file_summarizer_post", methods=['post'])
def file_summarizer_post():
    slide=request.files['slide']
    dt=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    full_path=slide_path+dt+".jpg"
    slide.save(full_path)
    aa=generate_full_report(full_path)
    return "<script>alert('Presentation closed');window.location='/user_home';</script>"

@app.route("/canvas")
def canvas():
    main3()
    return "<script>alert('Canvas closed');window.location='/user_home';</script>"

if __name__ == "__main__":
    app.run()