# flake8: NOQA
# This module breaks my OCD-ness in favor of readability
from datetime import datetime
from . import log

from . import models


def includeme(config):
    """
    Helper method to configure available routes for the application
    """

    config.add_static_view('static',                'occams.lab:static', cache_max_age=3600)

    config.add_route('labs',                         '/',                                factory=models.LabFactory)
    config.add_route('lab',                          '/{lab}',                           factory=models.LabFactory, traverse='/{lab}')
    # XXX: no edit yet becuase locations are hard-coded...
    config.add_route('lab_edit',                     '/{lab}/edit',                      factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_specimen_add',             '/{lab}/addspecimen',               factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_specimen_labels',          '/{lab}/specimen_labels',           factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_aliquot_labels',           '/{lab}/aliquot_labels',            factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_batched',                  '/{lab}/batched',                   factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_ready',                    '/{lab}/ready',                     factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_checkout',                 '/{lab}/checkout',                  factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_checkout_update',          '/{lab}/bulkupdate',                factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_checkout_receipt',         '/{lab}/checkoutreceipt',           factory=models.LabFactory, traverse='/{lab}')
    config.add_route('lab_checkin',                  '/{lab}/checkin',                   factory=models.LabFactory, traverse='/{lab}')

    log.debug('Routes configured')
