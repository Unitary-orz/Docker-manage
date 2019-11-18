from CTFd.models import db


class Containers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    image_tag = db.Column(db.String(80))
    container_id = db.Column(db.String(80))

    buildfile = db.Column(db.Text)

    def __init__(self, name, buildfile, image_tag, container_id):
        self.name = name
        self.buildfile = buildfile
        self.image_tag = image_tag
        self.container_id = container_id

    def __repr__(self):
        return "<Container ID:(0) {1}>".format(self.id, self.name, self.image_tag, self.container_id)
