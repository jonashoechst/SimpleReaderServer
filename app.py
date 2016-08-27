# -*- coding: utf-8 -*-

import os, datetime, glob, time

from flask_sqlalchemy import SQLAlchemy
from flask import *
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from apns import APNs, Payload, Frame

# Static Definitions
SIMPLE_CHARS="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
app_dir = os.path.realpath(os.path.dirname(__file__))

# load config
data = ""
with open(os.path.join(app_dir,'config.json')) as f:
    for line in f:
        data += line
json_config = json.loads(data)

# create Application
app = Flask(__name__)
app.secret_key = "0123456789"
app.config.update(json_config)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///"+app.config["DATABASE_FILE"]

try:
    import thumbs
except ImportError:
    app.config["RENDER_PREVIEWS"] = False
    
db = SQLAlchemy(app, session_options={'autocommit': True})
upload_path = os.path.join(app_dir, "static/"+app.config['UPLOAD_FOLDER'])
cert_file = os.path.join(app_dir, app.config["APS_CERT"])
apns = APNs(use_sandbox=app.config["APS_SANDBOX"], cert_file=cert_file, key_file=cert_file, enhanced=True)
   
# model definitions
class Device(db.Model):
    """ Database Model for a registered user device."""
    uid = db.Column(db.Text(36), primary_key=True)
    email = db.Column(db.Text(120))
    name = db.Column(db.Text(64))
    status = db.Column(db.Text(10))
    apns_token = db.Column(db.Text(64))
    screenshots = db.relationship("Screenshot")
    lastMessage = db.Column(db.Text(1024))
    
    def __unicode__(self):
        return self.uid+"("+self.name+")"
    
    def isAllowed(self):
        """ simple check, wether the device is allowed to update the feed. """
        if self.status == "green" or self.status == "yellow":
            return True
        if app.config["NEW_DEV_IS_ALLOWED"] and self.status == "new":
            return True
        return False
        
class Publication(db.Model):
    """ Database Model for created publications."""
    uid = db.Column(db.String(120), primary_key=True)
    title = db.Column(db.Text(120))
    shortDescription = db.Column(db.Text(2000))
    previewUrl = db.Column(db.String(200))
    pdfUrl = db.Column(db.String(200))
    releaseDate = db.Column(db.String(25))
    filesize = db.Column(db.String(25))
    category = db.Column(db.Text(25))
    
    def getDict(self):
        """ Returns all public variables of the publication."""
        return dict((key, value) for (key, value) in vars(self).iteritems() if key[0] != "_")
        # return {key: value for (key, value) in vars(self).iteritems() if key[0] != "_"}
    
    def generateUid(self):
        """ Generates an identifier for a new publication, based on the name and a running number."""
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
    """ Database Model for administrator accounts."""
    name = db.Column(db.Text(64))
    email = db.Column(db.Text(120), primary_key=True)
    pw_digest = db.Column(db.Text(64))
    
    def check_password(self, password):
        return check_password_hash(self.pw_digest, password)

class Screenshot(db.Model):
    """ Database model for screenshot entries. """
    gen_id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Text(36), db.ForeignKey('device.uid'))
    timestamp = db.Column(db.String(25))

def build_sample_db():
    """ creates a sample database for bootstraping or testing."""
    # db.drop_all()
    db.create_all()
    db.session.begin()

    admin = Admin()
    admin.email = "admin@example.org"
    admin.name = "Admin User"
    admin.pw_digest = generate_password_hash("password")
    db.session.add(admin)
    
    db.session.commit()

def send_apn(message, dev, pub=None):
    """ Sends an Apple Push Notification to a given registered device."""
    payload = craft_apn_payload(message, dev, pub=pub)
    if not payload:
        return False
    apns.gateway_server.send_notification(dev.apns_token, payload)
    return True
    
def send_multi_apn(message, devs, pub=None):
    """ Sends a bunch of Apple Push Notifications to given registered devices."""
    frame = Frame()
    identifier = 1
    expiry = time.time()+(60*60*24) # 1 day expire time
    priority = 10
    send = []
    unsend = []
    
    for dev in devs:
        payload = craft_apn_payload(message, dev, pub=pub)
        if payload:
            frame.add_item(dev.apns_token, payload, identifier, expiry, priority)
            send.append(dev.name)
        else:
            unsend.append(dev.name)

    apns.gateway_server.send_notification_multiple(frame)
    return (send, unsend)

def craft_apn_payload(message, dev, pub=None):
    """ Creates a Apple Push Notification Payload to be sent later."""
    # check if valid token is registered
    if len(dev.apns_token) != 64:
        return None
    custom_payload = {'status':dev.status, "lastMessage":dev.lastMessage}
    if pub and dev.isAllowed():
        custom_payload["pub"] = pub.getDict()
    return Payload(alert=message, sound="default", custom=custom_payload)
    
#
# Login decorator
def login_required(test):
    """ Login decorator for web administration."""
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
    """ Creates the admin login pages."""
    if request.method == "POST":
        admin = Admin.query.filter_by(email=request.form["email"]).first()
        if admin == None:
            flash("Falsche E-Mail Adresse.")
        elif not admin.check_password(request.form["password"]):
            flash("Falsches Passwort.")
        else:
            session["logged_in"] = True
            session["admin_name"] = admin.name
            session["admin_email"] = admin.email
            
            flash("Login erfolgreich!")
            return redirect (url_for("pubs"))
            
        return render_template("login.html")
        
    if request.method == "GET":
        return render_template("login.html")
        
#
# Admin Logout
@app.route("/admin/logout")
def logout():
    """ Logs out the user. """
    session.pop("logged_in", None)
    return redirect (url_for("home"))
              
#
# Administrate Devices
@app.route("/admin/devices", methods=["GET", "POST"])
@login_required
def devices():
    """ Creates the registered devices view."""
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
            textColor = u"grün"
        elif "yellow.x" in request.form:
            status = "yellow"
            textColor = "gelb"
        elif "red.x" in request.form:
            status = "red"
            textColor = "rot"
        elif "all" in request.form:
            devs = Device.query.all()
            okays = []
            fails = []
            for dev in devs:
                if send_apn(request.form["message_content"], dev):
                    okays.append(dev.name)
                else: 
                    fails.append(dev.name)
            flash(u"Push-Nachricht an "+", ".join(okays)+" erfolgreich gesendet.")
            flash(", ".join(fails)+" erlauben keine Push-Nachrichten.")
            return redirect(url_for("devices"))
        else:
            return "error in /admin/devices"

        if status != None:
            dev = Device.query.filter_by(uid=request.form["uid"]).first()
            db.session.begin()
            dev.status = status
            dev.lastMessage = "Du bist jetzt "+textColor+" eingestuft: "+request.form["message_content"]
            db.session.commit()
            
            success = send_apn(request.form["message_content"], dev)
            if success:
                flash(u"Gerät \""+dev.name+u"\" ist jetzt "+status+" eingestuft... Push-Nachricht gesendet: "+request.form["message_content"])
            else:
                flash(u"Gerät \""+dev.name+u"\" ist jetzt "+status+" eingestuft... "+dev.name+" erlaubt keine Push-Nachrichten." )
            return redirect(url_for("devices"))
#
# Administrate Admins
@app.route("/admin/admins", methods=["GET", "POST"])
@login_required
def admins():
    """ Creates the admin overview. """
    if request.method == "GET":
        return render_template("admins.html", admins=Admin.query.all())
    else:
        if "edit.x" in request.form:
            admin = Admin.query.filter_by(email=request.form["email"]).first()
            return redirect(url_for("edit_admin", email=request.form["email"]))
            
        elif "delete.x" in request.form:
            Admin.query.filter_by(email=request.form["email"]).delete()
            flash(u"Admin ("+request.form['email']+u") wurde erfolgreich gelöscht.")
            return redirect(url_for("admins"))

        else:
            return "error in /admin/admins"
            
#
# To create a new Admin
@app.route("/admin/new_admin", methods=["GET", "POST"])
@login_required
def new_admin():
    if request.method == "GET":
        return render_template("new_admin.html")
    else:
        db.session.begin()
        
        admin = Admin()
        admin.name = request.form['name']
        admin.email = request.form['email']
        admin.pw_digest = generate_password_hash(request.form['password'])
        db.session.add(admin)
        db.session.commit()
        
        flash(admin.name+u" wurde hinzugefügt.")
        return redirect(url_for("admins"))
#
# Edit Admin Account
@app.route("/admin/edit_admin/<email>", methods=["GET", "POST"])
@login_required
def edit_admin(email):
    if request.method == "GET":
        return render_template("edit_admin.html", admin=Admin.query.filter_by(email=email).first())
    else:
        admin = Admin.query.filter_by(email=request.form['email']).first()
        
        db.session.begin()
        admin.name = request.form['name']
        if request.form['password'] != "":
            admin.pw_digest = generate_password_hash(request.form['password'])
        db.session.commit()
        
        flash("Admin ("+admin.email+") wurde aktualisiert.")
        return redirect(url_for("admins"))
    
#
# Administrate Publications
@app.route("/admin/pubs", methods=["GET", "POST"])
@login_required
def pubs():
    """ Creates publication overview page."""
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
        elif "message.x" in request.form:
            pub = Publication.query.filter_by(uid=request.form['uid']).first()
            devs = Device.query.all()
            (send, unsend) = send_multi_apn(request.form["message_content"], devs, pub=pub)
            flash(u"Push-Nachricht an "+", ".join(send)+" erfolgreich gesendet.")
            flash(", ".join(unsend)+" erlauben keine Push-Nachrichten.")
            return redirect(url_for("pubs"))
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
    """ Creates the new publication page."""
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
        preview_ext = os.path.splitext(preview.filename)[1] if preview else ".jpg"
        preview_name = pub.uid + preview_ext
        preview_path = os.path.join(upload_path, preview_name)
        pub.previewUrl = url_for('static', filename=app.config['UPLOAD_FOLDER']+preview_name, _external=True)

        if app.config["RENDER_PREVIEWS"]:
            thumbs.save_thumbnail(pdf_path, preview_path, app.config["PREVIEW_RENDER_DPI"], app.config["PREVIEW_WIDTH"], app.config["PREVIEW_HEIGTH"])
        else:
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
    """ Creates the feed delievered to clients. """
    pubs = Publication.query.order_by(Publication.releaseDate.desc()).all()
    cleaned_pubs = [pub.getDict() for pub in pubs]
    if request.method == "GET":
        return json.dumps({"publications":cleaned_pubs})
    elif request.method == "POST":
        dev = Device.query.filter_by(uid=request.form["uid"]).first()
        return_dict = {}
        if dev == None:
            return_dict["status"] = "unknown"
        else:
            return_dict["status"] = dev.status
            return_dict["lastMessage"] = dev.lastMessage
            
        if return_dict["status"] == "green" or return_dict["status"] == "yellow" :
            return_dict["publications"] = cleaned_pubs
            return_dict["lastMessage"] = dev.lastMessage
            
        return json.dumps(return_dict)
    

#
# API Register Method
@app.route("/api/register", methods=["POST"])
def register():
    """ Allows a device to register itself to the server. """
    device = Device.query.filter_by(uid=request.form["uid"]).first()
    if device == None:
        device = Device()
        device.uid = request.form["uid"]
        device.status = "new"
        device.lastMessage = "Du bist neu angemeldet und musst erst freigeschaltet werden."
    if request.form["uid"] == "pknpt4sonz@test.acc":
        device.status = "green"
        
    device.name = request.form["name"]
    device.email = request.form["email"]
    device.apns_token = request.form["apns_token"]
        
    db.session.begin()
    db.session.add(device)
    db.session.commit()
        
    return json.dumps({"status":device.status, "lastMessage":device.lastMessage})
    
@app.route("/api/report", methods=["POST"])
def report():
    """ Takes screenshot reports of devices. """
    db.session.begin()
    screenshot = Screenshot()
    screenshot.uid = request.form["uid"]
    screenshot.timestamp = request.form["timestamp"]
    db.session.add(screenshot)

    device = Device.query.filter_by(uid=request.form["uid"]).first()
    if device.status == "green":
        device.status = "yellow"
        textColor = "gelb"
    elif device.status == "yellow":
        device.status = "red"
        textColor = "rot"
    elif app.config['NEW_DEV_IS_ALLOWED'] and device.status == "new":
        device.status = "yellow"
        textColor = "gelb"

    if len(device.screenshots) == 1: screenshotText = "einen Screenshot"
    else: str(len(device.screenshots))+" Screenshots"

    device.lastMessage = "Du hast "+screenshotText+" gemacht und bist jetzt "+textColor+" eingestuft."
    db.session.commit()
    return feed()

if __name__ == '__main__':
    
    # Build Sample DB and upload folder, if nonexistant
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db() 
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
        
    # Start app
    app.run(debug=True, host='0.0.0.0')

