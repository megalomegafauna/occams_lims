
from occams.lab import MessageFactory as _, \
                     SCOPED_SESSION_KEY
# from occams.lab.browser import crud
from z3c.form.interfaces import DISPLAY_MODE

from z3c.form import button, field, form as z3cform
from Products.Five.browser import BrowserView

from z3c.saconfig import named_scoped_session
from occams.lab import interfaces
from occams.lab import model
import zope.schema
from plone.z3cform import layout
from beast.browser import widgets
from zope.app.intid.interfaces import IIntIds
from occams.lab.browser import base
from beast.browser.crud import NestedFormView
from avrc.aeh.interfaces import IClinicalMarker
from zope.security import checkPermission
from Products.statusmessages.interfaces import IStatusMessage
from occams.lab import vocabularies
from sqlalchemy import or_, and_
from collective.beaker.interfaces import ISession
from zope.schema.vocabulary import SimpleTerm, \
                                   SimpleVocabulary
import os
SUCCESS_MESSAGE = _(u"Successfully updated")
PARTIAL_SUCCESS = _(u"Some of your changes could not be applied.")
NO_CHANGES = _(u"No changes made.")

class SpecimenFilterForm(base.FilterFormCore):
    """
    """
    @property
    def fields(self):
        if hasattr(self.context, 'omit_filter'):
            omitables = self.context.omit_filter
            return field.Fields(interfaces.ISpecimenFilterForm).omit(*omitables)
        return field.Fields(interfaces.ISpecimenFilterForm)

class SpecimenCoreButtons(base.CoreButtons):
    z3cform.extends(base.CoreButtons)

    @property
    def _stateModel(self):
        return model.SpecimenState

    @property 
    def sampletype(self):
        return u'specimen'
        
    @property 
    def _model(self):
        return model.Specimen


    def printLabels(self, action):
        selected = self.selected_items()
        label_list = []
        labelsheet = interfaces.ILabelPrinter(self.context.context)
        for id, item in selected:
            count = item.tubes
            if count is None or count < 1:
                count = 1
            for i in range(count):
                label_list.append(item)
        content = labelsheet.printLabelSheet(label_list)

        self.request.RESPONSE.setHeader("Content-type", "application/pdf")
        self.request.RESPONSE.setHeader("Content-disposition",
                                        "attachment;filename=labels.pdf")
        self.request.RESPONSE.setHeader("Cache-Control", "no-cache")
        self.request.RESPONSE.write(content)
        self.status = _(u"Your print is on its way. Refresh the page to view only unprinted labels.")


    @button.buttonAndHandler(_('Print Selected'), name='printed')
    def handlePrint(self, action):
        self.saveChanges(action)
        self.printLabels(action)
        return self.request.response.redirect(self.action)

    @button.buttonAndHandler(_('Save All Changes'), name='updated')
    def handleUpdate(self, action):
        self.saveChanges(action)
        return self.request.response.redirect(self.action)

class SpecimenCoreForm(base.CoreForm):
    """
    Base Crud form for editing specimen. Some specimen will need to be
    """
    @property
    def edit_schema(self):
        fields = field.Fields(interfaces.IViewableSpecimen, mode=DISPLAY_MODE).\
                    select('patient_our',
                             'patient_initials',
                             'cycle_title',
                             'visit_date', 
                             'tube_type',
                             )
        fields += field.Fields(interfaces.ISpecimen).\
                    select('specimen_type',
                             'tubes', 
                             'collect_date', 
                             'collect_time',
                             'notes'
                             )
        return fields

    def link(self, item, field):
        if field == 'patient_our':
            intids = zope.component.getUtility(IIntIds)
            patient = intids.getObject(item.patient.zid)
            url = '%s/specimen' % patient.absolute_url()
            return url
        elif field == 'visit_date' and getattr(item.visit, 'zid', None):
            intids = zope.component.getUtility(IIntIds)
            visit = intids.getObject(item.visit.zid)
            url = '%s/specimen' % visit.absolute_url()
            return url

    def updateWidgets(self):
        if self.update_schema is not None:
            if 'collect_time' in self.update_schema.keys():
                self.update_schema['collect_time'].widgetFactory = widgets.TimeFieldWidget
            if 'tubes' in self.update_schema.keys():
                self.update_schema['tubes'].widgetFactory = widgets.StorageFieldWidget

    def get_query(self):
        #makes testing a LOT easier
        session = named_scoped_session(SCOPED_SESSION_KEY)
        query = (
            session.query(model.Specimen)
                .join(model.Patient)
                .join(model.Cycle)
                .join(model.Visit)
                .join(model.SpecimenType)
                .join(model.SpecimenState)
                .order_by( model.Visit.visit_date.desc(), model.Patient.our, model.SpecimenType.name)
            )
        if self.display_state:
            query = query.filter(model.SpecimenState.name.in_(self.display_state))
        browsersession  = ISession(self.request)
        if 'specimen_type' in browsersession.keys():
            query = query.filter(model.SpecimenType.name == browsersession['aliquot_type'])
        if 'before_date' in browsersession.keys():
            if 'after_date' in browsersession.keys():
                query = query.filter(model.Specimen.collect_date >= browsersession['before_date'])
                query = query.filter(model.Specimen.collect_date <= browsersession['after_date'])
            else:
                query = query.filter(model.Specimen.collect_date == browsersession['before_date'])
        # if 'patient' in browsersession.keys():
        #     query = query.filter(or_(model.Specimen.patient.has(our=value), model.Specimen.patient.has(legacy_number=value)))
        if self.display_state and not browsersession.get('show_all', False):
            query = query.filter(model.SpecimenState.name.in_(self.display_state))
        return query

    # def filter(self):
    #     """ 
    #     """
    #     kw = ISession(self.request)
    #     filters = []
    #     retfilter = None
    #     for key, item in kw.items():
    #         if item is None or key not in ['specimen_type', 'before_date', 'after_date', 'patient','modify_name']:
    #             continue
    #         if not isinstance(item, list):
    #             item = [item]
    #         for value in item:
    #             filter = None
    #             if value is not None:
    #                 if key == 'specimen_type':
    #                     filter = model.SpecimenType == value
    #                 elif key == 'before_date':
    #                     filter = model.Specimen.collect_date <= value
    #                 elif key == 'after_date':
    #                     filter = model.Specimen.collect_date >= value
    #                 elif key == 'patient':
    #                     filter = or_(model.Specimen.patient.has(our=value), model.Specimen.patient.has(legacy_number=value))
    #                 elif key == 'modify_name':
    #                     if value is not None:
    #                         filter = model.Specimen.modify_name == unicode(value)
    #                     else:
    #                         filter = None
    #                 else:
    #                     print '%s is not a valid filter' % key
    #                     filter = None
    #                 if filter is not None:
    #                     filters.append(filter)
    #     if len(filters):
    #         retfilter = and_(*filters)
    #     return retfilter

class SpecimenForm(SpecimenCoreForm):
    """
    Primary view for a clinical lab object.
    """
    label = u"Specimen Pending Draw"
    description = _(u"Specimen pending processing.")

    def update(self):
        self.view_schema = field.Fields(interfaces.ISpecimen).select('state') + self.edit_schema
        super(base.CoreForm, self).update()

    @property
    def editform_factory(self):
        return SpecimenCoreButtons

    @property
    def display_state(self):
        return None


class SpecimenAddForm(z3cform.Form):
    label = _(u'Add Specimen')
    ignoreContext = True
    # redirect_url = os.path.join(context.absolute_url(), '@@specimen')

# #     @property
# #     def currentUser(self):
# #         return getSecurityManager().getUser().getId()
        
    def specimenVocabulary(self):
        ## get the terms for our Vocabulary

        context = self.context.aq_inner
        termlist = []
        for cycle in context.cycles:
            for specimen_type in cycle.study.specimen_types:
                term_title =u"%s -- %s" % (cycle.title, specimen_type.title)
                termlist.append(
                    SimpleTerm(
                        title= term_title,
                        token=str(term_title),
                        value=(cycle, specimen_type)
                        )
                    )
        return SimpleVocabulary(terms=termlist) 

    def update(self):
        request_specimen = zope.schema.List(
            title=_(u'Available Specimen'),
            value_type=zope.schema.Choice(
                           title=_(u'Available Specimen'),
                           description=_(u''),
                           source=self.specimenVocabulary()
                           )
            )
        request_specimen.__name__ = 'request_specimen'
        self.fields = field.Fields(request_specimen)
        super(SpecimenAddForm, self).update()

    @button.buttonAndHandler(_('Request More Specimen'), name='requestSpecimen')
    def requestSpecimen(self, action):
        data, errors = self.extractData()
        messages = IStatusMessage(self.request)
        if errors:
            messages.addStatusMessage(
                _(u'There was an error with your request.'),
                type='error'
                )
            return
        session = named_scoped_session(SCOPED_SESSION_KEY)
        drawstate = session.query(model.SpecimenState).filter_by(name=u'pending-draw').one()
        visitSQL = self.context.getSQLObj()
        for cycle, specimen_type in data['request_specimen']:
            newSpecimen = model.Specimen(
                    patient = visitSQL.patient,
                    cycle = cycle,
                    specimen_type = specimen_type,
                    state=drawstate,
                    collect_date = visitSQL.visit_date,
                    location_id = specimen_type.location_id,
                    tubes = specimen_type.default_tubes
                )
            session.add(newSpecimen)
            session.flush()
        return self.request.response.redirect(os.path.join(self.context.absolute_url(), '@@specimen'))


class SpecimenPatientForm(SpecimenForm):
    """
    Primary view for a clinical lab object.
    """
    label = u"Specimen Pending Draw"
    description = _(u"Specimen pending processing.")

    def get_query(self):
        query = super(SpecimenPatientForm, self).get_query()
        patient = IClinicalMarker(self.context).modelObj()
        query = query.filter(model.Specimen.patient == patient)
        return query

class SpecimenPatientView(BrowserView):
    """
    Primary view for a research lab object.
    """
    def getFilterForm(self):
        context = self.context.aq_inner
        context.omit_filter=['patient',]
        form = SpecimenFilterForm(context, self.request)
        view = NestedFormView(context, self.request)
        view = view.__of__(context)
        view.form_instance = form
        return view

    def getCrudForm(self):
        """
        Create a form instance.
        @return: z3c.form wrapped for Plone 3 view
        """
        context = self.context.aq_inner
        form = SpecimenPatientForm(context, self.request)
        if hasattr(form, 'getCount') and form.getCount() < 1:
            return None
        view = NestedFormView(context, self.request)
        view = view.__of__(context)
        view.form_instance = form
        return view

class SpecimenVisitForm(SpecimenForm):
    """
    Primary view for a clinical lab object.
    """
    label = u"Specimen Pending Draw"
    description = _(u"Specimen pending processing.")

    def get_query(self):
        query = super(SpecimenVisitForm, self).get_query()
        visit = IClinicalMarker(self.context).modelObj()
        query = query.filter(model.Specimen.visit == visit).filter(model.Specimen.collect_date == visit.visit_date)
        return query


class SpecimenVisitView(BrowserView):
    """
    Primary view for a research lab object.
    """
    def getFilterForm(self):
        context = self.context.aq_inner
        context.omit_filter=['patient', 'before_date', 'after_date']
        form = SpecimenFilterForm(context, self.request)
        view = NestedFormView(context, self.request)
        view = view.__of__(context)
        view.form_instance = form
        return view

    def getCrudForm(self):
        """
        Create a form instance.
        @return: z3c.form wrapped for Plone 3 view
        """
        context = self.context.aq_inner
        form = SpecimenVisitForm(context, self.request)
        if hasattr(form, 'getCount') and form.getCount() < 1:
            return None
        view = NestedFormView(context, self.request)
        view = view.__of__(context)
        view.form_instance = form
        return view

    def requestSpecimen(self):
        """ Create a form instance.
            Returns:
                z3c.form wrapped for Plone 3 view
        """
        context = self.context.aq_inner
        form = SpecimenAddForm(context, self.request)
        view = NestedFormView(context, self.request)
        view = view.__of__(context)
        view.form_instance = form
        return view