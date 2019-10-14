from landcover import db

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    answer = db.Column(db.Integer)
    ref_modis_answer = db.Column(db.Integer)

    def __repr__(self):
        return str(self.username)

    # def __repr__(self):
    #     return '<record {id}>: name {username}, xy({x}, {y}), answer {answer}'.format(
    #         self.id, self.username, self.x, self.y, self.answer)