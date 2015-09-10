# -*- coding: utf-8 -*-

import os, datetime

from flask_sqlalchemy import SQLAlchemy
from flask import *
from functools import wraps

from model import *

# Create Flask application
app = Flask(__name__)
app.secret_key = "0123456789"


app.config['UPLOAD_FOLDER'] = "static/uploads/"
app.config['HOSTNAME'] = "http://localhost:5000"

# Create database
app.config['DATABASE_FILE'] = 'SimpleReader.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+app.config['DATABASE_FILE']
app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app, session_options={'autocommit': True})


@app.route("/admin")
@app.route("/admin/")
def home():
    return redirect (url_for("pubs"))
    
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Admin.query.filter_by(username=request.form["username"]).first()
        if user == None:
            flash("Falscher Nutzername.")
        elif not user.check_password(request.form["password"]):
            flash("Falsches Passwort.")
        else:
            session["logged_in"] = True

            flash("Login erfolgreich!")
            return redirect (url_for("pubs"))
            
        return render_template("login.html")
        
    if request.method == "GET":
        return render_template("login.html")
        
@app.route("/admin/logout")
def logout():
    session.pop("logged_in", None)
    return redirect (url_for("home"))
    
def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if "logged_in" in session:
            return test(*args, **kwargs)
        else:
            flash("Login erforderlich!")
            return redirect(url_for("login"))
    return wrap    

@app.route("/admin/pubs", methods=["GET", "POST"])
@login_required
def pubs():
    if request.method == "GET":
        return render_template("pubs.html", pubs=Publication.query.all())
    else:
        print(str(request.form))
        if "edit.x" in request.form:
            return redirect(url_for("edit_pub", pub_uid=request.form["uid"]))
        elif "delete.x" in request.form:
            Publication.query.filter_by(uid=request.form['uid']).delete()
            # db.session.commit()
            
            return redirect(url_for("pubs"))
        elif "download.x" in request.form:
            pub = Publication.query.filter_by(uid=request.form['uid']).first()
            return redirect(pub.pdfUrl)
        else:
            return "Function not implemented."
            
@app.route("/admin/devices")
@login_required
def devices():
    return render_template("devices.html", devices=Device.query.all())

@app.route("/admin/edit_device/<device_uid>")
@login_required
def edit_device(device_uid):
    return render_template("edit_device.html", device=Device.query.filter_by(uid=device_uid).first())
    
@app.route("/admin/edit_pub/<pub_uid>", methods=["GET", "POST"])
@login_required
def edit_pub(pub_uid):
    if request.method == "GET":
        return render_template("edit_pub.html", pub=Publication.query.filter_by(uid=pub_uid).first())
    else:
        pub = Publication.query.filter_by(uid=request.form['uid']).first()
        pub.title = request.form['title']
        pub.shortDescription = request.form['shortDescription']
        pub.previewUrl = request.form['previewUrl']
        pub.pdfUrl = request.form['pdfUrl']
        pub.releaseDate = request.form['releaseDate']
        pub.filesize = request.form['filesize']
        pub.category = request.form['category']
        
        # db.session.commit()
        
        flash(pub.title+" wurde gespeichert.")
        return redirect(url_for("pubs"))
        
    
@app.route("/admin/new_pub", methods=["GET", "POST"])
@login_required
def new_pub():
    if request.method == "GET":
        return render_template("new_pub.html")
    else:
        pub = Publication()
        pub.title = request.form['title']
        pub.generateUid()
        pub.shortDescription = request.form['shortDescription']
        pub.category = request.form['category']
        pub.releaseDate = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00")
        
        pdf = request.files['pdf']
        pdf_ext = pdf.filename.split(".")[-1]
        pdf_path = os.path.join(upload_path, pub.uid+"."+pdf_ext)
        pub.pdfUrl = app.config['HOSTNAME']+"/"+app.config['UPLOAD_FOLDER']+pub.uid+"."+pdf_ext
        pdf.save(pdf_path)
        
        preview = request.files['preview']
        preview_ext = preview.filename.split(".")[-1]
        preview_path = os.path.join(upload_path, pub.uid+"."+preview_ext)
        pub.previewUrl = app.config['HOSTNAME']+"/"+app.config['UPLOAD_FOLDER']+pub.uid+"."+preview_ext
        preview.save(preview_path)
        
        filesize = os.stat(pdf_path).st_size / 1000.0 / 1000.0
        pub.filesize = "{0:.1f} MB".format(filesize)

        db.session.begin()
        db.session.add(pub)
        db.session.commit()
        
        flash(pub.title+u" wurde hinzugefügt.")
        return redirect(url_for("pubs"))
    
    
if __name__ == '__main__':
    # Build a sample db on the fly, if one does not exist yet.
    app_dir = os.path.realpath(os.path.dirname(__file__))
    
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db()
        
    upload_path = os.path.join(app_dir, app.config['UPLOAD_FOLDER'])
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    # Start app
    app.run(debug=True)

