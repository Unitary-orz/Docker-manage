from flask import current_app as app, render_template, request, redirect, jsonify, url_for, Blueprint
from CTFd.utils.decorators import admins_only
from CTFd.utils.user import is_admin
from CTFd.cache import cache
from CTFd.models import db
from .models import Containers
from CTFd.utils.helpers import get_errors

from . import utils


def load(app):
    app.db.create_all()
    admin_containers = Blueprint(
        'admin_containers', __name__, template_folder='templates')

    @admin_containers.route('/admin/containers', methods=['GET'])
    @admins_only
    def list_container():
        page = abs(request.args.get("page", 1, type=int))
        q = request.args.get("q")
        if q:
            field = request.args.get("field")
            containers = []
            errors = get_errors()
            if field == "id":
                if q.isnumeric():
                    containers = Containers.query.filter(
                        Containers.id == q).order_by(Containers.id.asc()).all()
                else:
                    containers = []
                    errors.append("Your ID search term is not numeric")
            elif field == "name":
                containers = (
                    Containers.query.filter(
                        containers.name.like("%{}%".format(q)))
                    .order_by(containers.id.asc())
                    .all()
                )

            return render_template(
                "containers.html",
                containers=containers,
                pages=0,
                curr_page=None,
                q=q,
                field=field,
            )
        page = abs(int(page))

        results_per_page = 50
        page_start = results_per_page * (page - 1)
        page_end = results_per_page * (page - 1) + results_per_page

        containers = Containers.query.order_by(
            Containers.id.asc()).slice(page_start, page_end).all()
        for c in containers:
            c.status, c.run_port = utils.container_status(c.container_id)
            # c.ports = ', '.join(utils.container_ports(
            #     c.container_id, verbose=True))
        count = db.session.query(db.func.count(Containers.id)).first()[0]
        pages = int(count / results_per_page) + (count % results_per_page > 0)

        return render_template('containers.html', containers=containers, pages=pages, curr_page=page)

    @admin_containers.route('/admin/containers/<int:ID>/stop', methods=['POST'])
    @admins_only
    def stop_container(ID):
        container = Containers.query.filter_by(id=ID).first_or_404()
        if utils.container_stop(container.container_id):
            return '1'
        else:
            return '0'

    @admin_containers.route('/admin/containers/<ID>/start', methods=['POST'])
    @admins_only
    def run_container(ID):
        container = Containers.query.filter_by(id=ID).first_or_404()
        status, ports = utils.container_status(container.container_id)
        if status == 'missing':
            if utils.image_run(container.name, container.ports):
                return '1'
            else:
                return '0'
        else:
            if utils.container_start(container.container_id):
                return '1'
            else:
                return '0'

    @admin_containers.route('/admin/containers/<int:ID>/delete', methods=['POST'])
    @admins_only
    def delete_container(ID):
        container = Containers.query.filter_by(id=ID).first_or_404()
        status, ports = utils.container_status(container.container_id)
        if status == 'missing':
            db.session.delete(container)
            db.session.commit()
            db.session.close()
        else:
            utils.container_delete(status, container.container_id)
        return '1'

    @admin_containers.route('/admin/containers/new', methods=['POST'])
    @admins_only
    def new_container():
        name = request.form.get('name')
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_'):
            return redirect(url_for('admin_containers.list_container'))
        buildfile = request.form.get('buildfile')
        files = request.files.getlist('files[]')
        utils.create_image(name=name, buildfile=buildfile, files=files)
        utils.image_run(name)
        return redirect(url_for('admin_containers.list_container'))

    @admin_containers.route('/admin/containers/import', methods=['POST'])
    @admins_only
    def import_container():
        name = request.form.get('name')
        ports = request.form.get('ports')
        print('port: ', ports, name)
        if not set(name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_/:.'):
            return redirect(url_for('admin_containers.list_container'))
        utils.import_image(name=name, ports=ports)
        return redirect(url_for('admin_containers.list_container'))

    @admin_containers.route('/admin/containers/import_all')
    @admins_only
    def import_image_all():
        utils.image_import_all()
        return redirect(url_for('admin_containers.list_container'))

    @admin_containers.route('/admin/containers/<int:ID>/update', methods=['POST'])
    @admins_only
    def update_port(ID):
        ports = request.form.get('ports')
        container = Containers.query.filter_by(id=ID).first_or_404()
        container.ports = ports
        db.session.commit()
        db.session.close()
        return redirect(url_for('admin_containers.list_container'))

    app.register_blueprint(admin_containers)
