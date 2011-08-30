from hive.lab import MessageFactory as _, \
                     vocabularies
from hive.lab.interfaces.lab import IFilter, \
                                    IFilterForm
from hive.lab.interfaces.labels import ILabel
from plone.directives import form
from plone.formwidget.contenttree import ObjPathSourceBinder
from z3c.relationfield.schema import RelationList, \
                                     RelationChoice
import zope.interface
import zope.schema
from z3c.form.interfaces import IAddForm

class ISpecimen(zope.interface.Interface):
    """ Mostly copied from aeh forms. Tons of work to do still. """

    dsid = zope.schema.Int(
        title=_(u'Data Store Id'),
        required=False,
        readonly=True
        )

    blueprint_zid = zope.schema.Int(
        title=_(u'Zid of the blueprint used during creation.'),
        required=False,
        )

    subject_zid = zope.schema.Int(title=_(u'Enrolled Subject Zope IntId'))

    protocol_zid = zope.schema.Int(title=_(u'Protocol\'s Zope IntId'))

    state = zope.schema.TextLine(
        title=_(u'State'),
        )

    date_collected = zope.schema.Date(
        title=_(u'Date Collected'),
        required=False,
        )

    time_collected = zope.schema.Time(
        title=_(u'Time Collected'),
        required=False,
        )

    type = zope.schema.TextLine(
        title=_(u'Specimen Type'),
        )

    destination = zope.schema.TextLine(
        title=_(u'Destination'),
        )

    tubes = zope.schema.Int(
        title=_(u'How many tubes?'),
        required=False,
        )

    tube_type = zope.schema.TextLine(
        title=_(u'Tube Type'),
        )

    notes = zope.schema.Text(
        title=_(u'Notes'),
        required=False,
        )
        
    def visit():
        pass


class IViewableSpecimen(form.Schema):

    state = zope.schema.Choice(
        title=_(u"State"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_state"),
        )
        
    patient_title = zope.schema.TextLine(
        title=u"Patient OUR#",
        readonly=True
        )

    patient_initials = zope.schema.TextLine(
        title=u"Initials",
        readonly=True
        )

    patient_legacy_number = zope.schema.TextLine(
        title=u"Patient Legacy (AEH) Number",
        readonly=True
        )

    study_title = zope.schema.TextLine(
        title=u"Study",
        readonly=True
        )

    protocol_title = zope.schema.TextLine(
        title=u"Protocol Week",
        readonly=True
        )

    study_week = zope.schema.TextLine(
        title=u"Study/Week",
        readonly=True
        )

    pretty_type = zope.schema.Choice(
        title=_(u"Specimen Type"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_type")
        )

    pretty_tube_type = zope.schema.Choice(
        title=_(u"Tube Type"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_tube_type"),
        )

class ISpecimenSupport(zope.interface.Interface):
    """
    Marker class for items that have specimen associated with them
    """
    def getSpecimen():
        """
        Function that provides specimen associated with the object
        """

class ISpecimenBlueprint(form.Schema, ISpecimenSupport, IFilter):
    """
    Blueprint the system can use to create specimen
    """

    type = zope.schema.Choice(
        title=_(u"Specimen Type"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_type")
        )

    default_tubes = zope.schema.Int(
        title=_(u'Default tubes count'),
        required=False,
        )

    tube_type = zope.schema.Choice(
        title=_(u"Tube Type"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_tube_type"),
        )

    destination = zope.schema.Choice(
        title=_(u"Destination"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_destination"),
        default=u"Richman Lab",
        )

class IBlueprintForSpecimen(zope.interface.Interface):
    """
    Find the blueprint associated with a Specimen
    """
    def getBlueprint():
        """
        Find the assocated Blueprint for this specimen
        """
        pass

class ISpecimenLabel(ILabel):
    """
    A Specimen Label
    """
    pretty_type = zope.schema.Choice(
        title=_(u"Specimen Type"),
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_type")
        )

class IAvailableSpecimen(form.Schema):
    """
    """
    form.fieldset('specimen', label=u"Specimen",
                  fields=['related_specimen'])

    related_specimen = RelationList(
        title=_(u'label_related_specimen', default=u'Available Specimen'),
        default=[],
        value_type=RelationChoice(
            title=u"Specimen", source=ObjPathSourceBinder(
                object_provides=ISpecimenBlueprint.__identifier__
            )
        ),
        required=False)
zope.interface.alsoProvides(IAvailableSpecimen, form.IFormFieldProvider)


class IRequiredSpecimen(form.Schema):
    """
    """
    form.fieldset('specimen', label=u"Specimen",
                  fields=['related_specimen'])

    related_specimen = zope.schema.List(
        title=_(u'label_related_specimen', default=u'Specimen'),
        default=[],
        value_type=zope.schema.Choice(title=u"Specimen",
                      source=vocabularies.SpecimenVocabulary()),
        required=False)
zope.interface.alsoProvides(IRequiredSpecimen, form.IFormFieldProvider)


class IRequestedSpecimen(ISpecimenSupport):
    """
    Marker class for items that require specimen
    """
    form.fieldset('specimen', label=u"Specimen",
                  fields=['require_specimen'])
                  
    form.omitted('require_specimen')
    form.no_omit(IAddForm, 'require_specimen')
    require_specimen = zope.schema.Bool(
        title=_(u"label_requested_specimen", default=u"Create Required Specimen?"),
        description=_(u"By default, the system will create specimen for items that require them. You can disable this feature by unchecking this box."),
        default=True,
        required=False
    )
    
    def getSpecimen():
        """
        Function that provides specimen associated with the object
        """

zope.interface.alsoProvides(IRequestedSpecimen, form.IFormFieldProvider)


class ISpecimenFilterForm(IFilterForm):
    """
    """
    type = zope.schema.Choice(title=u"Type of Specimen",
        source=vocabularies.SpecimenAliquotVocabulary(u"specimen_type"), required=False
        )

