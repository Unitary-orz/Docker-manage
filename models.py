from CTFd.models import db


class Containers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    image_tag = db.Column(db.String(80))
    container_id = db.Column(db.String(80))
    ports = db.Column(db.String(80))

    buildfile = db.Column(db.Text)

    def __init__(self, name, buildfile, image_id, container_id, ports):
        self.name = name
        self.buildfile = buildfile
        self.image_id = image_id
        self.container_id = container_id
        self.ports = ports

    def __repr__(self):
        return "<Container ID:(0) {1}>".format(self.id, self.name, self.image_id, self.container_id, self.ports)
