import os.path

from flask import Flask
from flask_admin import Admin
from flask_bootstrap import Bootstrap

from energy_saving.utils import settings

app = Flask(__name__, template_folder='../templates')
Bootstrap(app)
admin = Admin(app, name='energy_saving', template_mode='bootstrap3')
app.debug = settings.DEBUG
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
