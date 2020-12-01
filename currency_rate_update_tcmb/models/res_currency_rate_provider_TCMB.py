# Copyright 2020 Yiğit Budak (https://github.com/yibudak)
# Copyright 2009 Camptocamp
# Copyright 2009 Grzegorz Grzelak
# Copyright 2019 Brainbean Apps (https://brainbeanapps.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from collections import defaultdict
from datetime import date, timedelta
from urllib.request import urlopen
import xml.sax

from odoo import models, fields, api


class ResCurrencyRateProviderECB(models.Model):
    _inherit = 'res.currency.rate.provider'

    service = fields.Selection(
        selection_add=[('TCMB', 'Turkish Central Bank')],
    )

    @api.multi
    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != 'TCMB':
            return super()._get_supported_currencies()  # pragma: no cover

        # List of currencies obrained from:
        # https://www.tcmb.gov.tr/kurlar/today.xml
        return \
            [
                'USD', 'AUD', 'DKK', 'EUR', 'GBP', 'CHF', 'SEK', 'CAD',
                'KWD', 'NOK', 'SAR', 'JPY', 'BGN', 'RON', 'RUB', 'IRR',
                'CNY', 'PKR', 'QAR', 'XDR', 'TRY'
            ]

    @api.multi
    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != 'TCMB':
            return super()._obtain_rates(base_currency, currencies, date_from,
                                         date_to)  # pragma: no cover
        invert_calculation = False
        if base_currency != 'TRY':
            invert_calculation = True
            if base_currency not in currencies:
                currencies.append(base_currency)

        # Important : as explained on the TCMB web site, the currencies are
        # updated at 15:30 Istanbul time ; so, until 3:30 p.m. Istanbul time
        url = 'https://www.tcmb.gov.tr/kurlar/today.xml'

        handler = TCMBRatesHandler(currencies, date_from, date_to)
        with urlopen(url) as response:
            xml.sax.parse(response, handler)
        content = handler.content
        if invert_calculation:
            for k in content.keys():
                base_rate = float(content[k][base_currency])
                for rate in content[k].keys():
                    content[k][rate] = str(float(content[k][rate])/base_rate)
                    content[k]['TRY'] = str(1.0000/base_rate)
        return content


class TCMBRatesHandler(xml.sax.ContentHandler):
    def __init__(self, currencies, date_from, date_to):
        self.currencies = currencies
        self.date_from = date_from
        self.date_to = date_to
        self.date = None
        self.content = defaultdict(dict)

    def startElement(self, name, attrs):
        if name == 'Tarih_Date' and 'Tarih' in attrs:
            d = attrs['Tarih']
            d = '%s-%s-%s' % (  d[6:10],
                                d[3:5],
                                d[0:2])
            self.date = fields.Date.from_string(d)
            self.content[self.date.isoformat()]['TRY'] = '1.0000'
            self.rate_found = False
        elif name == 'Currency':
            self.currency = attrs['CurrencyCode']

        elif name == 'ForexBuying':
            self.rate_found = True

    def characters(self, content):
        if self.rate_found:
            rate = content
            if (self.date_from is None or self.date >= self.date_from) and \
                    (self.date_to is None or self.date <= self.date_to) and \
                    self.currency in self.currencies:
                self.content[self.date.isoformat()][self.currency] = rate
                self.rate_found = False
