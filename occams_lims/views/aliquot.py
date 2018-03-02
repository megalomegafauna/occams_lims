from datetime import date

import six
from pyramid.httpexceptions import HTTPFound, HTTPOk, HTTPForbidden
from pyramid.response import FileIter
from pyramid.view import view_config
from pyramid.session import check_csrf_token
import sqlalchemy as sa
from sqlalchemy import orm
import wtforms
from wtforms.ext.dateutil.fields import DateField
from wtforms_components import DateRange, TimeField

from occams.utils.forms import apply_changes
from occams.utils.pagination import Pagination
from occams_studies import models as studies

from .. import _, models
from ..labels import printLabelSheet
from ..validators import required_if
from .specimen import filter_specimen


ALIQUOT_LABEL_QUEUE = 'aliquot_label_queue'


class ALIQUOT_LABEL_SETTINGS:
    """
    These settings are based off:
        Cryo-Babies 1.28"x0.5" White, Order #LCRY-1700

    UCSD Richman Lab uses these types of labels, in the future we'll try and
    have configurable labels.
    """

    page_height = 11.0
    page_width = 8.5

    top_margin = 0.24
    side_margin = 0.77

    vert_pitch = 0.63
    horz_pitch = 1.4

    label_height = 0.5
    label_width = 1.28

    label_round = 0.1

    no_across = 5
    no_down = 18


@view_config(
    route_name='lims.aliquot',
    permission='view',
    renderer='../templates/aliquot/aliquot.pt')
def aliquot(context, request):
    db_session = request.db_session
    specimen_vals = filter_specimen(
        context, request, page_key='specimenpage', state='pending-aliquot')

    specimen = specimen_vals['specimen']
    template_values = [
        {'specimen': s, 'collect_date': date.today()}
        for s in specimen
    ]

    aliquot_vals = filter_aliquot(
        context, request, page_key='aliquotpage', state='pending')
    aliquot = aliquot_vals['aliquot']

    label_queue = request.session.setdefault(ALIQUOT_LABEL_QUEUE, set())

    class AliquotForm(wtforms.Form):
        # Copied from checkin.py About to replace everything so
        # taking this one shortcut
        def box_position_open(form, field):
            """
                Validates the box grid positions already selected
                is not occupied
            """
            message = "Box grid position {row} {col} already occupied by \
                       Aliquot id {id}"
            box_query = (
                    db_session.query(models.Aliquot)
                    .filter(models.Aliquot.box == form.box.data)
                    .filter(models.Aliquot.box_row == str(form.box_row.data))
                    .filter(models.Aliquot.box_column == form.box_column.data)
                    .first()
                    )

            if box_query is not None:
                if (form.id.data != box_query.id):
                    raise wtforms.ValidationError(message.format(
                        row=form.box_row.data,
                        col=form.box_column.data,
                        id=box_query.id))


        ui_selected = wtforms.BooleanField()
        id = wtforms.IntegerField(
            widget=wtforms.widgets.HiddenInput())
        amount = wtforms.DecimalField(
            places=1,
            validators=[wtforms.validators.required()])
        collect_date = DateField(
            validators=[
                wtforms.validators.required(),
                DateRange(min=date(1900, 1, 1))
            ])
        collect_time = TimeField(
            validators=[
                wtforms.validators.required(),
            ])
        freezer = wtforms.StringField(
            validators=[wtforms.validators.optional()])
        rack = wtforms.StringField(
            validators=[wtforms.validators.optional()])
        box_row = wtforms.IntegerField(
            validators=[wtforms.validators.optional(),
                        wtforms.validators.NumberRange(min=1, max=9,
                            message="Please enter number between 1-9")])
        box_column = wtforms.StringField(
            validators=[wtforms.validators.optional(),
                        wtforms.validators.Regexp('[abcdefghi]',
                        message= "Please enter lower case letter between a-i")])
        box = wtforms.StringField(
            validators=[wtforms.validators.optional(), box_position_open])
        notes = wtforms.TextAreaField(
            validators=[wtforms.validators.optional()])

    class SpecimenAliquotForm(wtforms.Form):
        """
        Similar form to Aliquot, except the fields are conditionally required
        if they are selected
        """

        ui_selected = wtforms.BooleanField()
        id = wtforms.IntegerField(
            widget=wtforms.widgets.HiddenInput())
        amount = wtforms.DecimalField(
            places=1,
            validators=[required_if('ui_selected')])
        collect_date = DateField(
            validators=[
                required_if('ui_selected'),
                DateRange(min=date(1900, 1, 1))
            ])
        collect_time = TimeField(
            validators=[required_if('ui_selected')])
        freezer = wtforms.StringField(
            validators=[wtforms.validators.optional()])
        rack = wtforms.StringField(
            validators=[wtforms.validators.optional()])
        box = wtforms.StringField(
            validators=[wtforms.validators.optional()])
        notes = wtforms.TextAreaField(
            validators=[wtforms.validators.optional()])

        count = wtforms.IntegerField(
            validators=[
                required_if('ui_selected'),
                wtforms.validators.optional()
            ]
        )
        aliquot_type_id = wtforms.SelectField(
            coerce=int,
            validators=[required_if('ui_selected')]
        )

        def __init__(self, *args, **kw):
            super(SpecimenAliquotForm, self).__init__(*args, **kw)

            specimen = None

            if 'obj' in kw:
                obj = kw['obj']
                if isinstance(obj, models.Specimen):
                    specimen = obj
                elif isinstance(obj, models.Aliquot):
                    specimen = obj.specimen
            elif 'specimen' in kw:
                specimen = kw['specimen']

            if specimen:
                self.aliquot_type_id.choices = [
                    (t.id, t.title)
                    for t in specimen.specimen_type.aliquot_types.values()]
            else:
                self.aliquot_type_id.choices = []

    class SpecimenCrudForm(wtforms.Form):
        specimen = wtforms.FieldList(wtforms.FormField(SpecimenAliquotForm))

    class AliquotCrudForm(wtforms.Form):
        aliquot = wtforms.FieldList(wtforms.FormField(AliquotForm))

    # Accomodate WTForm's inability to process multiple forms on the same page
    # by only passing in the appropriate formdata to the target form

    if 'template-form' in request.POST:
        specimen_formdata = request.POST
    else:
        specimen_formdata = None

    if 'aliquot-form' in request.POST:
        aliquot_formdata = request.POST
    else:
        aliquot_formdata = None

    specimen_form = SpecimenCrudForm(specimen_formdata, specimen=template_values)
    aliquot_form = AliquotCrudForm(aliquot_formdata, aliquot=aliquot)

    def update_print_queue():
        queued = 0
        for entry in aliquot_form.aliquot.entries:
            subform = entry.form
            if subform.ui_selected.data:
                id = subform.id.data
                if id in label_queue:
                    label_queue.discard(id)
                else:
                    queued += 1
                    label_queue.add(id)
                request.session.changed()
        return queued

    if request.method == 'POST' and check_csrf_token(request):

        if not request.has_permission('process'):
            raise HTTPForbidden

        if 'create' in request.POST and specimen_form.validate():
            state = (
                db_session.query(models.AliquotState)
                .filter_by(name='pending')
                .one())
            location = context
            processed_count = 0

            for i, entry in enumerate(specimen_form.specimen.entries):
                subform = entry.form

                # Yes, you are reading this correctly, the original
                # code said it needs to be selected AND set
                if not (subform.ui_selected.data and subform.count.data):
                    continue

                kw = subform.data
                kw['specimen'] = specimen[i]
                kw['state'] = state
                kw['location'] = location
                kw['inventory_date'] = kw['collect_date']
                kw['previous_location'] = location

                # clean up the dictionary
                for field in ['id', 'ui_selected', 'count']:
                    if field in kw.keys():
                        del kw[field]

                count = subform.count.data
                samples = [models.Aliquot(**kw) for i in range(count)]
                db_session.add_all(aliquot)
                db_session.flush()

                processed_count += len(samples)

            if processed_count:
                request.session.changed()
                request.session.flash(
                    _(u'Successfully created %d Aliquot' % processed_count),
                    'success')
            else:
                request.session.flash(_(u'No Aliquot created.'), 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'pending-draw' in request.POST:
            state_name = 'pending-draw'
            state = (
                db_session.query(models.SpecimenState)
                .filter_by(name=state_name)
                .one())
            transitioned_count = 0
            for i, subform in enumerate(specimen_form.specimen.entries):
                if subform.ui_selected.data:
                    specimen[i].state = state
                    transitioned_count += 1
            if transitioned_count:
                db_session.flush()
                request.session.flash(
                    _(u'${count} specimen have been changed to the '
                      u'status of ${state}.',
                        mapping={'count': transitioned_count,
                                 'state': state.title}),
                    'success')
            else:
                request.session.flash(u'Please select specimen', 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'aliquoted' in request.POST:
            state_name = 'aliquoted'
            state = (
                db_session.query(models.SpecimenState)
                .filter_by(name=state_name)
                .one())
            transitioned_count = 0
            for i, subform in enumerate(specimen_form.specimen.entries):
                if subform.ui_selected.data:
                    specimen[i].state = state
                    transitioned_count += 1
            if transitioned_count:
                db_session.flush()
                request.session.flash(
                    _(u'${count} specimen have been changed to the '
                      u'status of ${state}.',
                        mapping={'count': transitioned_count,
                                 'state': state.title}),
                    'success')
            else:
                request.session.flash(u'Please select specimen', 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'save' in request.POST and aliquot_form.validate():
            updated_count = 0
            for i, entry in enumerate(aliquot_form.aliquot.entries):
                if apply_changes(entry.form, aliquot[i]):
                    updated_count += 1
            if updated_count:
                request.session.flash(
                    _(u'Updated ${count} aliquot',
                        mapping={'count': updated_count}),
                    'success')
            else:
                request.session.flash(_(u'No changes made'), 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'queue' in request.POST and aliquot_form.validate():
            for i, subform in enumerate(aliquot_form.aliquot.entries):
                apply_changes(subform.form, aliquot[i])
            queue_count = update_print_queue()
            if queue_count:
                request.session.flash(
                    u'Aliquot print queue has changed.', 'success')
            else:
                request.session.flash(u'Please select aliquot', 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'checkin' in request.POST and aliquot_form.validate():
            transitioned_count = 0
            state = (
                db_session.query(models.AliquotState)
                .filter_by(name='checked-in')
                .one())
            for i, entry in enumerate(aliquot_form.aliquot.entries):
                apply_changes(entry.form, aliquot[i])
                if entry.ui_selected.data:
                    aliquot[i].state = state
                    transitioned_count += 1
            update_print_queue()
            if transitioned_count > 0:
                request.session.flash(
                    _(u'${count} aliquot have been changed to the status '
                      u'of ${state}.',
                        mapping={'count': transitioned_count,
                                 'state': state.title}),
                    'success')
            else:
                request.session.flash(u'Please select aliquot', 'warning')
            return HTTPFound(location=request.current_route_path())

        elif 'delete' in request.POST and aliquot_form.validate():
            deleted_count = 0
            for i, entry in enumerate(aliquot_form.aliquot.entries):
                apply_changes(entry.form, aliquot[i])
                if entry.ui_selected.data:
                    deleted_count += 1
                    db_session.delete(aliquot[i])
            update_print_queue()
            if deleted_count > 0:
                request.session.flash(
                    _(u'${count} aliquot have been deleted.',
                        mapping={'count': deleted_count}),
                    'success')
            else:
                request.session.flash(
                    _(u'Please select Aliquot'),
                    'warning')
            return HTTPFound(location=request.current_route_path())

    return {
        'filter_form': aliquot_vals['filter_form'],
        'has_aliquot': aliquot_vals['has_aliquot'],
        'aliquot': aliquot_vals['aliquot'],
        'aliquot_pager': aliquot_vals['pager'],
        'aliquot_form': aliquot_form,

        'has_labels_queued': len(label_queue),
        'label_queue': label_queue,

        'has_specimen': specimen_vals['has_specimen'],
        'specimen': specimen_vals['specimen'],
        'specimen_pager': specimen_vals['pager'],
        'specimen_form': specimen_form,
    }


def make_aliquot_label(aliquot):
    db_session = orm.object_session(aliquot)
    specimen = aliquot.specimen
    study = specimen.cycle.study
    cycle = specimen.cycle
    patient = specimen.patient
    pid = patient.pid
    collect_date_label = aliquot.collect_date.strftime('%m/%d/%Y')
    collect_time_label = aliquot.collect_time.strftime('%H:%M')
    study_label = study.short_title
    cycle_label = cycle.week or cycle.title
    type_label = aliquot.aliquot_type.name

    # A major blunder of LIMS is to not store the enrollment info the
    # sample was collected for, so we take a best guess by finding
    # a disinct enrollment based on the sample
    enrollment_query = (
        db_session.query(studies.Enrollment)
        .filter_by(patient=patient, study=study)
        .filter(studies.Enrollment.reference_number != sa.null())
    )

    try:
        enrollment = enrollment_query.one()
    except (orm.exc.NoResultFound, orm.exc.MultipleResultsFound):
        enrollment_number = u''
    else:
        enrollment_number = enrollment.reference_number

    if aliquot.amount:
        units = aliquot.aliquot_type.units or ''
        type_label += ' {}{}'.format(aliquot.amount, units)

    barcode = 0
    lines = [
        u'{}'.format(aliquot.id),
        u'{}   {}   {}'.format(aliquot.id, pid, enrollment_number),
        u'{} {}'.format(collect_date_label, collect_time_label),
        u'{} - {} - {}'.format(study_label, cycle_label, type_label)
    ]

    return barcode, lines


@view_config(
    route_name='lims.aliquot_labels',
    permission='view',
    renderer='../templates/modal-labels.pt')
def aliquot_labels(context, request):
    db_session = request.db_session

    label_queue = request.session.setdefault(ALIQUOT_LABEL_QUEUE, set())

    class PrintForm(wtforms.Form):
        startcol = wtforms.IntegerField(
            u'Starting Column Position',
            default=1,
            validators=[wtforms.validators.Optional()])
        startrow = wtforms.IntegerField(
            u'String Row Position',
            default=1,
            validators=[wtforms.validators.Optional()])

    form = PrintForm(request.POST)

    if request.method == 'POST' and check_csrf_token(request):
        if not request.has_permission('process'):
            raise HTTPForbidden

        if 'print' in request.POST and form.validate():
            if label_queue:
                query = (
                    db_session.query(models.Aliquot)
                    .join(models.Specimen)
                    .filter(models.Aliquot.id.in_(label_queue))
                    .order_by(
                        models.Specimen.patient_id,
                        models.Aliquot.aliquot_type_id,
                        models.Aliquot.id))
                printables = iter(make_aliquot_label(s) for s in query)

                stream = six.StringIO()
                printLabelSheet(
                    stream,
                    u'{} labels'.format(context.title),
                    printables,
                    ALIQUOT_LABEL_SETTINGS,
                    form.startcol.data,
                    form.startrow.data)
                stream.flush()
                stream.seek(0)

                request.session[ALIQUOT_LABEL_QUEUE] = set()
                request.session.changed()

                response = request.response
                response.content_type = 'application/pdf'
                response.content_disposition = 'attachment;filename=labels.pdf'
                response.app_iter = FileIter(stream)
                return response

        elif 'clear' in request.POST:
            request.session[ALIQUOT_LABEL_QUEUE] = set()
            request.session.changed()
            request.session.flash(u'Your Queue has been cleared', 'info')
            next = request.current_route_path(_route_name='lims.specimen')
            if request.is_xhr:
                return HTTPOk(json={'__next__': next})
            else:
                return HTTPFound(location=next)

    return {
        'form': form,
        'count': len(label_queue)
    }


def filter_aliquot(context, request, state, page_key='page', omit=None):
    db_session = request.db_session

    omit = set(omit or [])

    types_query = db_session.query(models.AliquotType).order_by('title')
    available_types = [(t.id, t.title) for t in types_query]

    states_query = db_session.query(models.AliquotState).order_by('title')
    available_states = [(s.id, s.title) for s in states_query]

    cycles_query = db_session.query(studies.Cycle).order_by('title')
    available_cycles = [(s.id, s.title) for s in cycles_query]

    class FilterForm(wtforms.Form):

        pid = wtforms.StringField(
            _(u'PID'),
            validators=[wtforms.validators.Optional()])

        aliquot_types = wtforms.SelectMultipleField(
            _(u'Aliquot Types'),
            choices=available_types,
            coerce=int,
            validators=[wtforms.validators.Optional()])

        aliquot_states = wtforms.SelectMultipleField(
            _(u'Aliquot States'),
            choices=available_states,
            coerce=int,
            validators=[wtforms.validators.Optional()])

        visit_cycles = wtforms.SelectMultipleField(
            _(u'Visit Cycles'),
            choices=available_cycles,
            coerce=int,
            validators=[wtforms.validators.Optional()])

        from_ = DateField(
            _(u'From Date'),
            validators=[
                wtforms.validators.Optional(),
                DateRange(min=date(1900, 1, 1))
            ])

        to = DateField(
            _(u'To Date'),
            validators=[
                wtforms.validators.Optional(),
                DateRange(min=date(1900, 1, 1))
            ])

        freezer = wtforms.StringField(
            _(u'Freezer'),
            validators=[wtforms.validators.Optional()])

        rack = wtforms.StringField(
            _(u'Rack'),
            validators=[wtforms.validators.Optional()])

        box = wtforms.StringField(
            _(u'Box'),
            validators=[wtforms.validators.Optional()])

    filter_form = FilterForm(request.GET)

    for name in omit:
        del filter_form[name]

    # TODO: There is a possibility that the listing might get
    #       updated between requests, we need to make sure the same
    #       listing is repeatable...
    query = (
        db_session.query(models.Aliquot)
        .join(models.Aliquot.specimen)
        .join(models.Specimen.patient)
        .join(models.Aliquot.aliquot_type)
        .join(models.Aliquot.state)
        .filter(
            (models.Aliquot.location == context)
            | (models.Aliquot.previous_location == context))
        .order_by(
            studies.Patient.pid,
            models.AliquotType.title,
            models.Aliquot.id))

    if 'pid' not in omit and filter_form.pid.data:
        query = query.filter(
            studies.Patient.pid.ilike('%s%%' % filter_form.pid.data))

    if 'aliquot_types' not in omit and filter_form.aliquot_types.data:
        query = query.filter(
            models.Aliquot.aliquot_type_id.in_(filter_form.aliquot_types.data))

    if 'aliquot_states' not in omit and filter_form.aliquot_states.data:
        query = query.filter(
            models.Aliquot.state_id.in_(filter_form.aliquot_states.data))
    else:
        query = query.filter(models.AliquotState.name == state)

    if 'visit_cycles' not in omit and filter_form.visit_cycles.data:
        query = query.filter(
            models.Aliquot.specimen.has(
                models.Specimen.cycle_id.in_(filter_form.visit_cycles.data)))

    if 'from_' not in omit and filter_form.from_.data:
        query = query.filter(
            (models.Aliquot.collect_date >= filter_form.from_.data)
            | (models.Aliquot.inventory_date >= filter_form.from_.data))

    if 'to' not in omit and filter_form.to.data:
        query = query.filter(
            (models.Aliquot.collect_date <= filter_form.to.data)
            | (models.Aliquot.inventory_date <= filter_form.to.data))

    if 'freezer' not in omit and filter_form.freezer.data:
        query = query.filter(
            models.Aliquot.freezer == filter_form.freezer.data)

    if 'rack' not in omit and filter_form.rack.data:
        query = query.filter(models.Aliquot.rack == filter_form.rack.data)

    if 'box' not in omit and filter_form.box.data:
        query = query.filter(models.Aliquot.box == filter_form.box.data)

    total_count = query.count()
    pager = Pagination(request.GET.get(page_key), 20, total_count)

    aliquot = query.offset(pager.offset).limit(pager.per_page).all()

    return {
        'filter_form': filter_form,
        'full_query': query,
        'aliquot': aliquot,
        'has_aliquot': len(aliquot) > 0,
        'pager': pager,
    }
