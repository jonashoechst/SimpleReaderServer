# -*- coding: utf-8 -*-

from app import db
from werkzeug.security import generate_password_hash, check_password_hash

SIMPLE_CHARS="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

class Device(db.Model):
    uid = db.Column(db.Text(36), primary_key=True)
    email = db.Column(db.Text(120))
    name = db.Column(db.Text(64))
    status = db.Column(db.Text(10))
    
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
    db.drop_all()
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
    