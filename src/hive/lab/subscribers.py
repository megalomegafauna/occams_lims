
from OFS.interfaces import IObjectWillBeRemovedEvent
from five import grok

from z3c.saconfig import named_scoped_session

from avrc.aeh.interfaces import IVisit
from avrc.aeh.interfaces import IClinicalMarker
from avrc.data.store.interfaces import IDataStore

from hive.lab import Logger as log

@grok.subscribe(IVisit, IObjectWillBeRemovedEvent)
def handlePatientRemoved(item, event):
    """ Retires samples when a Patient is about to removed from
        the Plone content tree.
        
        TODO: It's still unclear how this exactly is going to work, as it would
        be nice to mark the specimen as destroyed. But this highly depends
        on the workflow (lab technitians ACTUALLY destroying the samples).
        Should an error occurr in the future, this would probably be the
        starting point. 
    """
    zid = IClinicalMarker(item).zid
    msg = 'Retiring specimen on patient delete is not implemented Visit(zid=%d)'
    log.warn(msg % zid)
