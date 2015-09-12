# -*- coding: utf-8 -*-

import os, datetime, glob

from flask_sqlalchemy import SQLAlchemy
from flask import *
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from apns import APNs, Payload

# Static Definitions
PORT = 5000
SIMPLE_CHARS="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
app_dir = os.path.realpath(os.path.dirname(__file__))

# create Application
app = Flask(__name__)
app.secret_key = "0123456789"
app.config['UPLOAD_FOLDER'] = "uploads/"
app.config['SCREENSHOT_FOLDER'] = "screenshots/"
app.config['HOSTNAME'] = "http://localhost:"+str(PORT)
app.config['DATABASE_FILE'] = 'SimpleReader.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+app.config['DATABASE_FILE']
app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app, session_options={'autocommit': True})
upload_path = os.path.join(app_dir, "static/"+app.config['UPLOAD_FOLDER'])
screenshot_path = os.path.join(app_dir, "static/"+app.config['SCREENSHOT_FOLDER'])

cert_file = os.path.join(app_dir, 'aps_development_combined.pem')
apns = APNs(use_sandbox=True, cert_file=cert_file, key_file=cert_file)
   
# model definitions
class Device(db.Model):
    uid = db.Column(db.Text(36), primary_key=True)
    email = db.Column(db.Text(120))
    name = db.Column(db.Text(64))
    status = db.Column(db.Text(10))
    apns_token = db.Column(db.Text(64))
    
    def __unicode__(self):
        return self.uid+"("+self.name+")"
        
class Publication(db.Model):
    uid = db.Column(db.String(120), primary_key=True)
    title = db.Column(db.Text(120))
    shortDescription = db.Column(db.Text(2000))
    previewUrl = db.Column(db.String(200))
    pdfUrl = db.Column(db.String(200))
    releaseDate = db.Column(db.String(25))
    filesize = db.Column(db.String(25))
    category = db.Column(db.Text(25))
    
    def generateUid(self):
        if self.uid != None:
            return self.uid
            
        new_uid = "".join([c for c in self.title if c in SIMPLE_CHARS]).encode("utf-8").lower()
        # filter(lambda x: x in SIMPLE_CHARS, self.title).encode("utf-8")
        num = 0
        
        other_pub = Publication.query.filter_by(uid=new_uid+str(num)).first()
        while(other_pub != None):
            num = num + 1
            other_pub = Publication.query.filter_by(uid=new_uid+str(num)).first()
            
        self.uid = new_uid+str(num)
        
        return self.uid
    
    def __unicode__(self):
        return "Publication: "+self.uid+"("+self.title+")"
    
class Admin(db.Model):
    username = db.Column(db.Text(64), primary_key=True)
    name = db.Column(db.Text(64))
    email = db.Column(db.Text(120))
    pw_digest = db.Column(db.Text(64))
    
    def check_password(self, password):
        return check_password_hash(self.pw_digest, password)

def build_sample_db():
    # db.drop_all()
    db.create_all()
    db.session.begin()
    
    pub = Publication()
    pub.title = u"Sonneblättche"
    pub.generateUid()
    pub.shortDescription = u"Bei dieser Hitze kommt man ordentlich ins schwitzen. Nichts desto trotz ist das Sommer Hesseblättche jetzt fertig. \n\nDie Highlights:\n - duftes Quiz\n - schniekes Rätsel\n - lässige Gewinne\n\nViel Spaß beim lesen!"
    pub.previewUrl = "https://hb.jonashoechst.de/static/sommer2015@2x.jpg"
    pub.pdfUrl = "https://hb.jonashoechst.de/static/sommer2015.pdf"
    pub.releaseDate = "2015-07-10T18:00:00+01:00"
    pub.filesize = "22.6 MB"
    pub.category = u"Hesseblättche"
    db.session.add(pub)
    
    admin = Admin()
    admin.username = "admin"
    admin.email = "admin@example.org"
    admin.name = "Admin"
    admin.pw_digest = generate_password_hash("password")
    db.session.add(admin)
    
    db.session.commit()

def send_apn(message, dev):
    if len(dev.apns_token) != 64:
        print("Token: "+dev.apns_token+" len: "+str(len(dev.apns_token)))
        return False
    payload = Payload(alert=message, sound="default", custom={'status':dev.status})
    apns.gateway_server.send_notification(dev.apns_token, payload)
    return True
    
#
# Login decorator
def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if "logged_in" in session:
            return test(*args, **kwargs)
        else:
            flash("Login erforderlich!")
            return redirect(url_for("login"))
    return wrap
   

#
# Login decorator
@app.route("/admin")
def home():
    return redirect (url_for("pubs"))
    
#
# Admin Login
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
        
#
# Admin Logout
@app.route("/admin/logout")
def logout():
    session.pop("logged_in", None)
    return redirect (url_for("home"))
              
#
# Administrate Devices
@app.route("/admin/devices", methods=["GET", "POST"])
@login_required
def devices():
    if request.method == "GET":
        return render_template("devices.html", devices=Device.query.all())
    else:
        if "message.x" in request.form:
            dev = Device.query.filter_by(uid=request.form["uid"]).first()
            success = send_apn(request.form["message_content"], dev)
            if success:
                flash(u"Push-Nachricht an "+dev.name+" erfolgreich gesendet.")
            else: 
                flash(dev.name+"erlaubt keine Push-Nachrichten.")      
            return redirect(url_for("devices"))
            
        elif "delete.x" in request.form:
            Device.query.filter_by(uid=request.form["uid"]).delete()
            flash(u"Gerät ("+request.form['uid']+u") wurde erfolgreich gelöscht.")
            return redirect(url_for("devices"))
            
        elif "green.x" in request.form:
            status = "green"
        elif "yellow.x" in request.form:
            status = "yellow"
        elif "red.x" in request.form:
            status = "red"
            
        if status != None:
            dev = Device.query.filter_by(uid=request.form["uid"]).first()
            db.session.begin()
            dev.status = status
            db.session.commit()
            
            success = send_apn(request.form["message_content"], dev)
            if success:
                flash(u"Gerät \""+dev.name+u"\" ist jetzt "+status+" eingestuft... Push-Nachricht gesendet: "+request.form["message_content"])
            else:
                flash(u"Gerät \""+dev.name+u"\" ist jetzt "+status+" eingestuft... "+dev.name+" erlaubt keine Push-Nachrichten." )
            return redirect(url_for("devices"))
#
# Administrate Publications
@app.route("/admin/pubs", methods=["GET", "POST"])
@login_required
def pubs():
    if request.method == "GET":
        return render_template("pubs.html", pubs=Publication.query.order_by(Publication.releaseDate.desc()).all())
    else:
        print(str(request.form))
        if "edit.x" in request.form:
            return redirect(url_for("edit_pub", pub_uid=request.form["uid"]))
        elif "delete.x" in request.form:
            Publication.query.filter_by(uid=request.form['uid']).delete()
            for root, dirs, files in os.walk(upload_path):
                for file in files:
                    if (request.form['uid']+".") in file:
                        os.remove(os.path.join(root, file))

            flash(u"Publikation ("+request.form['uid']+u") wurde erfolgreich gelöscht.")
            return redirect(url_for("pubs"))
        elif "download.x" in request.form:
            pub = Publication.query.filter_by(uid=request.form['uid']).first()
            return redirect(pub.pdfUrl)
        else:
            return "Function not implemented."
         
            
#
# Edit single Publication
@app.route("/admin/edit_pub/<pub_uid>", methods=["GET", "POST"])
@login_required
def edit_pub(pub_uid):
    if request.method == "GET":
        return render_template("edit_pub.html", pub=Publication.query.filter_by(uid=pub_uid).first())
    else:
        pub = Publication.query.filter_by(uid=request.form['uid']).first()
        
        db.session.begin()
        pub.title = request.form['title']
        pub.shortDescription = request.form['shortDescription']
        pub.previewUrl = request.form['previewUrl']
        pub.pdfUrl = request.form['pdfUrl']
        pub.releaseDate = request.form['releaseDate']
        pub.filesize = request.form['filesize']
        pub.category = request.form['category']
        db.session.commit()
        
        flash(pub.title+" wurde gespeichert.")
        return redirect(url_for("pubs"))
        
    
#
# To create a new Publication
@app.route("/admin/new_pub", methods=["GET", "POST"])
@login_required
def new_pub():
    if request.method == "GET":
        return render_template("new_pub.html")
    else:
        db.session.begin()
        
        pub = Publication()
        pub.title = request.form['title']
        pub.generateUid()
        pub.shortDescription = request.form['shortDescription']
        pub.category = request.form['category']
        pub.releaseDate = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00")
        
        pdf = request.files['pdf']
        pdf_name = pub.uid + os.path.splitext(pdf.filename)[1]
        pdf_path = os.path.join(upload_path, pdf_name)
        pub.pdfUrl = url_for('static', filename=app.config['UPLOAD_FOLDER']+pdf_name, _external=True)
        pdf.save(pdf_path)
        
        preview = request.files['preview']
        preview_name = pub.uid + os.path.splitext(preview.filename)[1]
        preview_path = os.path.join(upload_path, preview_name)
        pub.previewUrl = url_for('static', filename=app.config['UPLOAD_FOLDER']+preview_name, _external=True)
        preview.save(preview_path)

        filesize = os.stat(pdf_path).st_size / 1000.0 / 1000.0
        pub.filesize = "{0:.1f} MB".format(filesize)

        db.session.add(pub)
        db.session.commit()
        
        flash(pub.title+u" wurde hinzugefügt.")
        return redirect(url_for("pubs"))
    
    

#
# API Feed Method
@app.route("/api/feed", methods=["POST"])
def feed():
    pubs = Publication.query.order_by(Publication.releaseDate.desc()).all()
    cleaned_pubs = [{key: value for (key, value) in vars(pub).iteritems() if key[0] != "_"} for pub in pubs]
    if request.method == "GET":
        return json.dumps({"publications":cleaned_pubs})
    elif request.method == "POST":
        dev = Device.query.filter_by(uid=request.form["uid"]).first()
        return_dict = {}
        if dev == None:
            return_dict["status"] = "unknown"
        else:
            return_dict["status"] = dev.status
            
        if return_dict["status"] == "green" or return_dict["status"] == "yellow" :
            return_dict["publications"] = cleaned_pubs
            
        return json.dumps(return_dict)
    

#
# API Register Method
@app.route("/api/register", methods=["POST"])
def register():
    device = Device.query.filter_by(uid=request.form["uid"]).first()
    if device == None:
        device = Device()
        device.uid = request.form["uid"]
        device.status = "new"
        
    device.name = request.form["name"]
    device.email = request.form["email"]
    device.apns_token = request.form["apns_token"]
        
    db.session.begin()
    db.session.add(device)
    db.session.commit()
        
    return json.dumps({"status":device.status})
    
@app.route("/api/report", methods=["POST"])
def report():
    device = Device.query.filter_by(uid=request.form["uid"]).first()

    pngdata = request.form['pngdata']
    png_name = request.form["timestamp"]+"-"+request.form["uid"]+".png"
    png_path = os.path.join(screenshot_path, png_name)
    file = open(png_path, "w")
    file.write(pngdata)
    file.close()
    return "success"

if __name__ == '__main__':
    
    # Build Sample DB and upload folder, if nonexistant
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db() 
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    if not os.path.exists(screenshot_path):
        os.makedirs(screenshot_path)
        
    # Start app
    app.run(debug=True, port=PORT)

