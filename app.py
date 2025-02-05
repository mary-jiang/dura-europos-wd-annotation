# -*- coding: utf-8 -*-

import collections
import decorator
import flask
import iiif_prezi.factory
import json
from markupsafe import Markup
import mwapi
import mwoauth
import os
import random
import re
import requests
import requests_oauthlib
import stat
import string
import toolforge
import urllib.parse
import yaml
import math

from exceptions import WrongDataValueType
import messages

import queries
from consts import *

app = flask.Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')

user_agent = toolforge.set_user_agent('dura-europos-wd-annotation')

requests_session = requests.Session()
requests_session.headers.update({
    'Accept': 'application/json',
    'User-Agent': user_agent,
})

default_property = 'P18'

depicted_properties = {
    # first label is used in dropdown,
    # second forms “… with no region specified” list label
    'P180': ['depicts', 'Depicted'],
    # 'P9664': ['named place on map', 'Named places on map'],
    # note: currently, these must be item-type properties;
    # support for other data types (e.g. P1684 inscription) needs more work
}
app.add_template_global(lambda: depicted_properties, 'depicted_properties')

@decorator.decorator
def read_private(func, *args, **kwargs):
    try:
        f = args[0]
        fd = f.fileno()
    except AttributeError:
        pass
    except IndexError:
        pass
    else:
        mode = os.stat(fd).st_mode
        if (stat.S_IRGRP | stat.S_IROTH) & mode:
            raise ValueError(f'{getattr(f, "name", "config file")} is readable to others, '
                             'must be exclusively user-readable!')
    return func(*args, **kwargs)

has_config = app.config.from_file('config.yaml', load=read_private(yaml.safe_load), silent=True)
if has_config:
    consumer_token = mwoauth.ConsumerToken(app.config['OAUTH']['consumer_key'], app.config['OAUTH']['consumer_secret'])
else:
    print('config.yaml file not found, assuming local development setup')
    app.secret_key = 'fake'

def anonymous_session(domain):
    host = 'https://' + domain
    return mwapi.Session(host=host, user_agent=user_agent, formatversion=2)

def authenticated_session(domain):
    if 'oauth_access_token' not in flask.session:
        return None
    host = 'https://' + domain
    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                    resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
    return mwapi.Session(host=host, auth=auth, user_agent=user_agent, formatversion=2)


@decorator.decorator
def enableCORS(func, *args, **kwargs):
    rv = func(*args, **kwargs)
    response = flask.make_response(rv)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST':
        if 'item_id' in flask.request.form:
            item_id = parse_item_id_input(flask.request.form['item_id'])
            property_id = flask.request.form.get('property_id')
            if 'manifest' in flask.request.form or 'preview' in flask.request.form:
                manifest_url = full_url('iiif_manifest_with_property', item_id=item_id, property_id=property_id or default_property)
                if 'manifest' in flask.request.form:
                    return flask.redirect(manifest_url)
                else:
                    mirador_protocol = 'https' if manifest_url.startswith('https') else 'http'
                    mirador_url = mirador_protocol + '://tools.wmflabs.org/mirador/?manifest=' + manifest_url
                    return flask.redirect(mirador_url)
            else:
                if property_id:
                    return flask.redirect(flask.url_for('item_and_property', item_id=item_id, property_id=property_id))
                else:
                    return flask.redirect(flask.url_for('item', item_id=item_id))
        if 'iiif_region' in flask.request.form:
            iiif_region = flask.request.form['iiif_region']
            property_id = flask.request.form.get('property_id')
            if property_id:
                return flask.redirect(flask.url_for('iiif_region_and_property', iiif_region=iiif_region, property_id=property_id))
            else:
                return flask.redirect(flask.url_for('iiif_region', iiif_region=iiif_region))
        if 'image_title' in flask.request.form:
            image_title = parse_image_title_input(flask.request.form['image_title'])
            return flask.redirect(flask.url_for('file', image_title=image_title))
    return flask.render_template('index.html')

def parse_item_id_input(input):
    # note: “item” here (and elsewhere in the tool, though not sure if *everywhere* else) refers to any non-MediaInfo entity type
    pattern = r'''
    (?: # can begin with a wd:, data:, or entity page URL prefix
    http://www\.wikidata\.org/entity/ |
    https://www\.wikidata\.org/wiki/Special:EntityData/ |
    https://www\.wikidata\.org/wiki/
    )?
    ( # the entity ID itself
    [QPL][1-9][0-9]* |
    L[1-9][0-9]*-[FS][1-9][0-9]*
    )
    (?: # optional remaining URL parts
    [?#].*
    )?
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        return match.group(1)  # unquote() not needed, group 1 cannot contain % characters

    url = urllib.parse.urlparse(input)
    if url.scheme == 'https' and url.hostname == 'www.wikidata.org' and url.path == '/w/index.php':
        query = urllib.parse.parse_qs(url.query)
        title = query.get('title', [''])[-1]
        pattern = r'''
        (Q[1-9][0-9]*) |
        Property:(P[1-9][0-9]*) |
        Lexeme:(L[1-9][0-9]*)
        '''
        if match := re.fullmatch(pattern, title, re.VERBOSE):
            return match.group(1)

    flask.abort(400, Markup(r'Cannot parse an entity ID from <kbd>{}</kbd>.').format(input))

def parse_image_title_input(input):
    if '.' in input and ':' not in input:
        return input.replace(" ", "_")

    if input.startswith('File:'):
        return input[len('File:'):].replace(' ', '_')

    pattern = r'''
    (?: # URL prefix
    https://commons\.wikimedia\.org/wiki/File: |
    https://commons\.wikimedia\.org/wiki/Special:FilePath/
    )
    ( # the file name itself, without File:
    [^/?#]* # very lenient :)
    )
    (?: # optional remaining URL parts
    [?#].*
    )?
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        return urllib.parse.unquote(match.group(1))

    url = urllib.parse.urlparse(input)
    if url.scheme == 'https' and url.hostname == 'commons.wikimedia.org' and url.path == '/w/index.php':
        query = urllib.parse.parse_qs(url.query)
        title = query.get('title', [''])[-1]
        if title.startswith('File:'):
            return title[len('File:'):]

    pattern = r'''
    (?: # can begin with an sdc: or sdcdata: URL prefix
    https://commons\.wikimedia\.org/entity/ |
    https://commons\.wikimedia\.org/wiki/Special:EntityData/
    )?
    ( # the entity ID itself
    M[1-9][0-9]*
    )
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        entity_id = match.group(1)  # unquote() not needed, group 1 cannot contain % characters
        session = anonymous_session('commons.wikimedia.org')
        title = session.get(action='query',
                            pageids=[entity_id[1:]],
                            redirects=True,
                            formatversion=2)['query']['pages'][0]['title']
        return title[len('File:'):].replace(' ', '_')

    flask.abort(400, Markup(r'Cannot parse a file name from <kbd>{}</kbd>.').format(input))

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://www.wikidata.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    return flask.redirect(redirect)

@app.route('/oauth-callback')
def oauth_callback():
    oauth_request_token = flask.session.pop('oauth_request_token', None)
    if oauth_request_token is None:
        return flask.render_template('oauth-callback-without-request-token.html',
                                     already_logged_in='oauth_access_token' in flask.session,
                                     query_string=flask.request.query_string.decode(flask.request.url_charset))
    access_token = mwoauth.complete('https://www.wikidata.org/w/index.php', consumer_token, mwoauth.RequestToken(**oauth_request_token), flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    flask.session.pop('_csrf_token', None)
    return flask.redirect(flask.url_for('index'))

@app.route('/logout')
def logout():
    flask.session.pop('oauth_request_token', None)
    return flask.redirect(flask.url_for('index'))

@app.route('/item/<item_id>')
def item(item_id):
    return item_and_property(item_id, property_id=default_property)

@app.route('/item/<item_id>/<property_id>')
def item_and_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)
    if 'image_title' not in item:
        return flask.render_template('item-without-image.html', **item)
    return flask.render_template('item.html', **item)

@app.route('/iiif/<item_id>/manifest.json')
def iiif_manifest(item_id):
    return flask.redirect(flask.url_for('iiif_manifest_with_property', item_id=item_id, property_id=default_property))

@app.route('/iiif/<item_id>/<property_id>/manifest.json')
@enableCORS
def iiif_manifest_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_description=True, include_metadata=True)
    if 'image_title' not in item:
        return '', 404
    manifest = build_manifest(item)
    return flask.jsonify(manifest.toJSON(top=True))

@app.route('/iiif/<item_id>/list/annotations.json')
def iiif_annotations(item_id):
    return iiif_annotations_with_property(item_id, property_id=default_property)

@app.route('/iiif/<item_id>/<property_id>/list/annotations.json')
@enableCORS
def iiif_annotations_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)

    url = flask.url_for('iiif_annotations_with_property',
                        item_id=item_id,
                        property_id=property_id,
                        _external=True,
                        _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'))
    annolist = {
        '@id': url,
        '@type': 'sc:AnnotationList',
        'label': 'Annotations for ' + item['label']['value'],
        'resources': []
    }

    if 'image_title' not in item:
        return flask.jsonify(annolist)

    canvas_url = url[:-len('list/annotations.json')] + 'canvas/c0.json'
    # Although the pct canvas is OK for the image API, we need to target
    # canvas coordinates with the annotations, so we need the w,h
    image_info = load_image_info(item['image_title'])
    width, height = int(image_info['thumbwidth']), int(image_info['thumbheight'])

    for depicted in item['depicteds']:
        if 'item_id' not in depicted:
            continue  # somevalue/novalue not supported for now
        link = 'http://www.wikidata.org/entity/' + Markup.escape(depicted['item_id'])
        label = depicted['label']['value']
        # We can put a lot more in here, but minimum for now, and ensure works in Mirador
        anno = {
            '@id': '#' + depicted['statement_id'],
            '@type': 'oa:Annotation',
            'motivation': 'identifying',
            'on': canvas_url,
            'resource': {
                '@id': link,
                'format': 'text/plain',
                'chars': label
            }
        }
        iiif_region = depicted.get('iiif_region', None)
        if iiif_region:
            parts = iiif_region.replace('pct:', '').split(',')
            x = int(float(parts[0]) * width / 100)
            y = int(float(parts[1]) * height / 100)
            w = int(float(parts[2]) * width / 100)
            h = int(float(parts[3]) * height / 100)
            anno['on'] = anno['on'] + '#xywh=' + ','.join(str(d) for d in [x, y, w, h])
        annolist['resources'].append(anno)
    return flask.jsonify(annolist)

@app.route('/iiif_region/<iiif_region>')
def iiif_region(iiif_region):
    return iiif_region_and_property(iiif_region, default_property)

@app.route('/iiif_region/<iiif_region>/<property_id>')
def iiif_region_and_property(iiif_region, property_id):
    iiif_region_string = '"' + iiif_region.replace('\\', '\\\\').replace('"', '\\"') + '"'
    property_claim_predicates = ' '.join(f'p:{property_id}' for property_id in depicted_properties)
    query = '''
      SELECT DISTINCT ?item WHERE {
        VALUES ?p { %s }
        ?item ?p [ pq:P2677 %s ].
      }
    ''' % (property_claim_predicates, iiif_region_string)
    query_results = requests_session.get('https://query.wikidata.org/sparql',
                                         params={'query': query}).json()

    items = []
    items_without_image = []
    for result in query_results['results']['bindings']:
        item_id = result['item']['value'][len('http://www.wikidata.org/entity/'):]
        item = load_item_and_property(item_id, property_id, include_depicteds=True)
        if 'image_title' not in item:
            items_without_image.append(item_id)
        else:
            items.append(item)

    return flask.render_template('iiif_region.html', items=items, items_without_image=items_without_image)

@app.route('/file/<image_title>')
def file(image_title):
    image_title_ = image_title.replace(' ', '_')
    if image_title_.startswith('File:'):
        image_title_ = image_title_[len('File:'):]
    if image_title_ != image_title:
        return flask.redirect(flask.url_for('file', image_title=image_title_, **flask.request.args))
    file = load_file(image_title.replace('_', ' '))
    if not file:
        return flask.render_template('file-not-found.html', title=image_title), 404
    return flask.render_template('file.html', **file)

@app.route('/api/v1/depicteds_html/file/<image_title>')
@enableCORS
def file_depicteds_html(image_title):
    file = load_file(image_title.replace('_', ' '))
    if not file:
        return flask.render_template('file-not-found.html', title=image_title), 404
    return flask.render_template('depicteds.html', depicteds=file['depicteds'])

@app.route('/api/v1/add_statement/<domain>', methods=['POST'])
def api_add_statement(domain):
    language_codes = request_language_codes()
    entity_id = flask.request.form.get('entity_id')
    snaktype = flask.request.form.get('snaktype')
    item_id = flask.request.form.get('item_id')
    property_id = flask.request.form.get('property_id', 'P180')
    csrf_token = flask.request.form.get('_csrf_token')
    if not entity_id or not snaktype or not csrf_token:
        return 'Incomplete form data', 400
    if (snaktype == 'value') != (item_id is not None):
        return 'Inconsistent form data', 400
    if snaktype not in {'value', 'somevalue', 'novalue'}:
        return 'Bad snaktype', 400
    if property_id not in depicted_properties:
        return 'Bad property ID', 400

    if csrf_token != flask.session['_csrf_token']:
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    depicted = {
        'snaktype': snaktype,
        'property_id': property_id,
    }
    if snaktype == 'value':
        value = json.dumps({'entity-type': 'item', 'id': item_id})
        depicted['item_id'] = item_id
        labels = load_labels([item_id], language_codes)
        depicted['label'] = labels[item_id]
    else:
        value = None
        if snaktype == 'somevalue':
            depicted['label'] = messages.somevalue(language_codes[0])
        elif snaktype == 'novalue':
            depicted['label'] = messages.novalue(language_codes[0])
        else:
            raise ValueError('Unknown snaktype')
    try:
        response = session.post(action='wbcreateclaim',
                                entity=entity_id,
                                snaktype=snaktype,
                                property=property_id,
                                value=value,
                                token=token)
    except mwapi.errors.APIError as error:
        return str(error), 500
    statement_id = response['claim']['id']
    depicted['statement_id'] = statement_id
    return flask.jsonify(depicted=depicted,
                         depicted_item_link=depicted_item_link(depicted))

@app.route('/api/v2/add_qualifier/<domain>', methods=['POST'])
def api_add_qualifier(domain):
    statement_id = flask.request.form.get('statement_id')
    iiif_region = flask.request.form.get('iiif_region')
    csrf_token = flask.request.form.get('_csrf_token')
    qualifier_hash = flask.request.form.get('qualifier_hash')  # optional
    if not statement_id or not iiif_region or not csrf_token:
        return 'Incomplete form data', 400

    if csrf_token != flask.session['_csrf_token']:
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    try:
        response = session.post(action='wbsetqualifier', claim=statement_id, property='P2677',
                                snaktype='value', value=('"' + iiif_region + '"'),
                                **({'snakhash': qualifier_hash} if qualifier_hash else {}),
                                summary='region drawn manually using [[d:User:Lucas Werkmeister/Wikidata Image Positions|Wikidata Image Positions tool]]',
                                token=token)
    except mwapi.errors.APIError as error:
        if error.code == 'no-such-qualifier':
            return 'This region does not exist (anymore) – it may have been edited in the meantime. Please try reloading the page.', 500
        return str(error), 500
    # find hash of qualifier
    for qualifier in response['claim']['qualifiers']['P2677']:
        if qualifier['snaktype'] == 'value' and qualifier['datavalue']['value'] == iiif_region:
            return flask.jsonify(qualifier_hash=qualifier['hash'])
    return flask.jsonify(qualifier_hash=None)

@app.route('/dashboard/<page>')
def dashboard(page):
    page = int(page)
    entries = query_dashboard(page)

    if page < 10:
        range_1 = [1, 10]
        range_2 = []
        range_3 = [678, 683]
    elif page > 673:
        range_1 = [1, 5]
        range_2 = []
        range_3 = [673, 683]
    else:
        range_1 = [1, 5]
        range_2 = [page - 4, page + 4]
        range_3 = [678, 683]

    page_ranges = [range_1, range_2 , range_3]

    processed_entries = []
    # load all item ids and extract 
    language_codes = request_language_codes()
    props = ['claims']
    session = anonymous_session('www.wikidata.org')
    api_response = session.get(action='wbgetentities',
                               props=props,
                               ids=entries,
                               languages=language_codes)
    for entry in entries:
        processed_entry = {
            'item_id': entry 
        }
        image_datavalue = best_value(api_response['entities'][entry], default_property)
        processed_entry.update(load_image(image_datavalue['value'], language_codes))
        processed_entries.append(processed_entry)

    return flask.render_template('dashboard.html', entries=processed_entries, ranges=page_ranges)

@app.route('/projectleaddashboard/<page>')
def project_lead_dashboard(page): 
    if deny_access():
        return flask.render_template('no-access.html')
    
    total_items = queries.query_db(queries.get_number_of_objects_annotated())
    total_items = queries.jsonify_rows(total_items)[0]['COUNT(DISTINCT item_id)']
    pages = math.ceil(total_items / 10)

    # fetch all objects thathave been annotated
    result = queries.query_db(queries.get_all_annotated_objects())
    output = queries.jsonify_rows(result)
    objects = {} # key = object id, value = set of users who annotated that object

    for row in output:
        item_id = row['item_id']
        if objects.get(item_id) is None:
            objects[item_id] = set()
        objects[item_id].add(row['username'])

    end_index = int(page) * 10
    start_index = end_index - 10 if end_index > 10 else 0

    keys = list(objects.keys())[start_index:end_index]
    trimmed_objects = {}
    for key in keys:
        trimmed_objects[key] = objects[key]

    # need to get the images and stuff of each object
    objects_info = {}
    language_codes = request_language_codes()
    props = ['claims']
    session = anonymous_session('www.wikidata.org')
    api_response = session.get(action='wbgetentities',
                               props=props,
                               ids=keys,
                               languages=language_codes)
    for key in keys:
        entry = {
            'item_id': key
        }
        image_datavalue = best_value(api_response['entities'][key], default_property)
        entry.update(load_image(image_datavalue['value'], language_codes))
        objects_info[key] = entry
    return flask.render_template('project-lead-dashboard.html', objects=trimmed_objects, objects_info=objects_info, pages=pages)

@app.route('/annotations/<page>')
def annotations(page):
    # this is a page of a user's local annotations in dashboard format
    userinfo = get_userinfo()
    if not userinfo:
        return flask.render_template('not-logged-in.html')

    username = userinfo['name']
    total_items = queries.query_db(queries.get_number_of_objects_annotated_by_user(), params=[username])
    total_items = queries.jsonify_rows(total_items)[0]['COUNT(DISTINCT item_id)']
    pages = math.ceil(total_items / 10)

    # get all the objects that have been annotated by this user
    result = queries.query_db(queries.get_all_annotated_objects_by_user(), params=[username])
    output = queries.jsonify_rows(result)
    keys = [x['item_id'] for x in output]

    end_index = int(page) * 10
    start_index = end_index - 10 if end_index > 10 else 0

    keys = keys[start_index:end_index]

    # get actual object information for key list
    language_codes = request_language_codes()
    props = ['claims']
    session = anonymous_session('www.wikidata.org')
    api_response = session.get(action='wbgetentities',
                               props=props,
                               ids=keys,
                               languages=language_codes)
    objects = []
    for key in keys:
        processed_entry = {
            'item_id': key
        }
        image_datavalue = best_value(api_response['entities'][key], default_property)
        processed_entry.update(load_image(image_datavalue['value'], language_codes))

        # check if this thing has been approved or not
        approved_query = queries.jsonify_rows(queries.query_db(queries.get_approval(), params=[username, key]))
        approved = True if approved_query and approved_query[0]['approved'] == 1 else False
        processed_entry['approved'] = approved
        
        objects.append(processed_entry)

    return flask.render_template('annotations.html', pages=pages, objects=objects)

@app.route('/api/v1/add_statement_local/<domain>', methods=['POST'])
def api_add_statement_local(domain):
    language_codes = request_language_codes()
    entity_id = flask.request.form.get('entity_id')
    snaktype = flask.request.form.get('snaktype')
    item_id = flask.request.form.get('item_id')
    property_id = flask.request.form.get('property_id', 'P180')
    csrf_token = flask.request.form.get('_csrf_token')
    reference_type = flask.request.form.get("reference_type")
    reference_value = flask.request.form.get("reference_value")
    pages_value = flask.request.form.get("pages_value")
    
    if not entity_id or not snaktype or not csrf_token:
        return 'Incomplete form data', 400
    if (snaktype == 'value') != (item_id is not None):
        return 'Inconsistent form data', 400
    if snaktype not in {'value', 'somevalue', 'novalue'}:
        return 'Bad snaktype', 400
    if property_id not in depicted_properties:
        return 'Bad property ID', 400

    if csrf_token != flask.session['_csrf_token']:
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403

    # construct response
    depicted = {
        'snaktype': snaktype,
        'property_id': property_id,
    }
    if snaktype == 'value':
        depicted['item_id'] = item_id
        labels = load_labels([item_id], language_codes)
        depicted['label'] = labels[item_id]
    else:
        if snaktype == 'somevalue':
            depicted['label'] = messages.somevalue(language_codes[0])
        elif snaktype == 'novalue':
            depicted['label'] = messages.novalue(language_codes[0])
        else:
            raise ValueError('Unknown snaktype')

    # save this statement locally
    username = get_userinfo()['name']
    if reference_type and reference_value:
        if pages_value:
            queries.query_db(queries.add_statement_with_reference_and_page(), params=[entity_id, property_id, item_id, snaktype, username, reference_type, reference_value, pages_value])
        else:
            queries.query_db(queries.add_statement_with_reference(), params=[entity_id, property_id, item_id, snaktype, username, reference_type, reference_value])
    else:
        queries.query_db(queries.add_statement(), params=[entity_id, property_id, item_id, snaktype, username])

    # update response with the statement id that was added
    result = queries.query_db(queries.get_latest_statement())
    statement_id = queries.jsonify_rows(result)[0]['statement_id']
    depicted['statement_id'] = statement_id
    return flask.jsonify(depicted=depicted,
                         depicted_item_link=depicted_item_link(depicted))

@app.route('/api/v2/add_qualifier_local/<domain>', methods=['POST'])
def api_add_qualifier_local(domain):
    statement_id = flask.request.form.get('statement_id')
    iiif_region = flask.request.form.get('iiif_region')
    csrf_token = flask.request.form.get('_csrf_token')
    qualifier_hash = flask.request.form.get('qualifier_hash')  # optional
    if not statement_id or not iiif_region or not csrf_token:
        return 'Incomplete form data', 400

    if csrf_token != flask.session['_csrf_token']:
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403
    
    queries.query_db(queries.add_qualifier(), params=[statement_id, iiif_region, (qualifier_hash if qualifier_hash else "")])

    return flask.jsonify(qualifier_hash=None)

@app.route('/api/v1/delete_statement_local', methods=['POST'])
def api_delete_statement_local():
    statement_id = flask.request.form.get('statement_id')
    if not statement_id:
        return 'Incomplete form data', 400
    
    queries.query_db(queries.delete_statement(), params=[statement_id])
    queries.query_db(queries.delete_comment_with_statement_id(), params=[statement_id])
    
    return flask.jsonify({'success': True})

@app.route('/api/v2/delete_qualifier_local', methods=['POST'])
def api_delete_qualifier_local():
    statement_id = flask.request.form.get('statement_id')
    if not statement_id:
        return 'Incomplete form data', 400

    queries.query_db(queries.delete_qualifier(), params=[statement_id])
    
    statement = queries.jsonify_rows(queries.query_db(queries.get_statement(), params=[statement_id]))[0]
    language_codes = request_language_codes()   
    depicted = {
            'snaktype': statement['snaktype'],
            'statement_id': statement['statement_id'],
            'property_id': statement['property_id'],
    }
    if statement['snaktype'] == 'value':
        depicted['item_id'] = statement['value_id']
        labels = load_labels([statement['value_id']], language_codes)
        depicted['label'] = labels[statement['value_id']]
    else:
        if statement['snaktype'] == 'somevalue':
            depicted['label'] = messages.somevalue(language_codes[0])
        elif statement['snaktype'] == 'novalue':
            depicted['label'] = messages.novalue(language_codes[0])
        else:
            raise ValueError('Unknown snaktype')
  
    return flask.jsonify(depicted=depicted,
                         depicted_item_link=depicted_item_link(depicted))

@app.route("/api/v2/add_comment", methods=['POST'])
def api_add_comment():
    statement_id = flask.request.form.get('statement_id')
    comment = flask.request.form.get('comment')
    item_id = flask.request.form.get('item_id')
    username = flask.request.form.get('username')

    userinfo = get_userinfo()
    if not userinfo:
        return 'Not logged in', 403
    project_lead_username = userinfo['name']

    queries.query_db(queries.add_comment(), params=[statement_id, comment, project_lead_username, item_id, username])
    return flask.jsonify(project_lead_username=project_lead_username, comment=comment, statement_id=statement_id)

@app.route('/api/v2/get_comments', methods=["POST"])
def api_get_comments():
    item_id = flask.request.form.get('item_id')
    username = flask.request.form.get('username')
    result = queries.query_db(queries.get_comments(), params=[item_id, username])
    return queries.jsonify_rows(result)

@app.route('/api/v2/get_comments_own_user', methods=["POST"])
def api_get_comments_own_user():
    item_id = flask.request.form.get('item_id')
    userinfo = get_userinfo()
    if not userinfo:
        return 'Not logged in', 403
    result = queries.query_db(queries.get_comments(), params=[item_id, userinfo['name']])
    return queries.jsonify_rows(result)

@app.route('/api/v2/upload_annotations', methods=["POST"])
def api_upload_annotation():
    item_id = flask.request.form.get('item_id')
    # username = flask.request.form.get('username')
    userinfo = get_userinfo()
    if not userinfo:
        return 'Not logged in', 403
    username = userinfo['name']

    result = upload_local_annotations(item_id, username)
    if result[1] == 200:
        # delete related things from the local stuff
        delete_local_annotations(item_id, username)
        delete_all_comments_and_approval(item_id, username)

    return result 

@app.route('/permissions')
def permissions():
    userinfo = get_userinfo()
    is_logged_in = False
    is_project_lead = False
    already_requested = False
    users = []
    if userinfo:
        result = queries.query_db(queries.is_project_lead(), params=[userinfo['name']]) 
        output = queries.jsonify_rows(result)[0]
        if output['is_project_lead'] == 1:
            is_project_lead = True
            result = queries.query_db(queries.get_all_project_lead_requests())
            output = queries.jsonify_rows(result)
            for row in output:
                users.append(row['username'])
        else:
            result = queries.query_db(queries.get_request_status(), params=[userinfo['name']])
            output = queries.jsonify_rows(result)[0]
            if output['requested_lead_status'] == 1:
                already_requested = True
        is_logged_in = True

    if not is_logged_in:
        return flask.render_template('not-logged-in.html')

    return flask.render_template('permissions.html', is_logged_in=is_logged_in, is_project_lead=is_project_lead, users=users, already_requested=already_requested)

@app.route('/permissions/request', methods=["POST"])
def permissions_request():
    # this is can only be called by a logged in contributor
    userinfo = get_userinfo()
    queries.query_db(queries.request_project_lead(), params=[userinfo['name']])
    return flask.jsonify({'success': True})

@app.route('/permissions/approve', methods=['POST'])
def permissions_approve():
    # this can only be called by a logged in project lead
    username = flask.request.form.get('username')
    queries.query_db(queries.set_project_lead(), params=[username])
    # make sure that we derequest the user as we already approved them
    queries.query_db(queries.unrequest_project_lead(), params=[username])
    return flask.jsonify({'success': True})

@app.route('/comment/<item_id>/<username>')
def comment(item_id, username):
    if deny_access():
        return flask.render_template('no-access.html')

    item = load_item_and_property(item_id=item_id, property_id=default_property, include_depicteds=True, local_only=True, username=username)
    return flask.render_template('comment.html', **item)

@app.route('/api/v2/emailuser', methods=["POST"])
def api_email_user():
    username = flask.request.form.get('username')
    item_id = flask.request.form.get('item_id')
    subject = f"Annotations for object {item_id} approved"
    link = "https://dura-europos-wd-annotation.toolforge.org" + str(flask.url_for('item', item_id=item_id))
    text = f"Your annotations for object {item_id} have been approved on the Dura Europos Wikidata Annotation Tool. Please navigate to {link} or type in {item_id} into the lookup bar when you visit the homepage at https://dura-europos-wd-annotation.toolforge.org/"

    # update the database
    queries.query_db(queries.add_approval(), params=[username, item_id, True])

    session = authenticated_session("www.wikidata.org")
    if session is None:
        return 'Not logged in', 403
    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    try: 
        response = session.post(action="emailuser",
                                target=username,
                                subject=subject,
                                text=text,
                                token=token)
    except mwapi.errors.APIError as error:
        return str(error), 500

    return "Success", 200    

@app.route('/api/v2/get_approved', methods=["POST"])
def api_get_approved():
    username = flask.request.form.get('username')
    item_id = flask.request.form.get('item_id')

    if not username:
        userinfo = get_userinfo()
        username = userinfo['name']

    result = queries.query_db(queries.get_approval(), params=[username, item_id])
    if result:
        result = queries.jsonify_rows(result)
    else:
        result = [{'approved': 0}]
    return flask.jsonify(result)

# https://iiif.io/api/image/2.0/#region
@app.template_filter()
def iiif_region_to_style(iiif_region):
    try:
        if iiif_region == 'full':
            return 'left: 0px; top: 0px; width: 100%; height: 100%;'
        if iiif_region.startswith('pct:'):
            left, top, width, height = iiif_region[len('pct:'):].split(',')
            z_index = int(1_000_000 / (float(width) * float(height)))
            return 'left: %s%%; top: %s%%; width: %s%%; height: %s%%; z-index: %s;' % (left, top, width, height, z_index)
        left, top, width, height = iiif_region.split(',')
        z_index = int(1_000_000_000 / (int(width) * int(height)))
        return 'left: %spx; top: %spx; width: %spx; height: %spx; z-index: %s;' % (left, top, width, height, z_index)
    except ValueError:
        flask.abort(400, Markup('Invalid IIIF region <kbd>{}</kbd> encountered. Remove the invalid qualifier manually, then reload.').format(iiif_region))

@app.template_filter()
def user_link(user_name):
    return (Markup(r'<a href="https://www.wikidata.org/wiki/User:') +
            Markup.escape(user_name.replace(' ', '_')) +
            Markup(r'">') +
            Markup(r'<bdi>') +
            Markup.escape(user_name) +
            Markup(r'</bdi>') +
            Markup(r'</a>'))

@app.template_global()
def item_link(item_id, label):
    return (Markup(r'<a href="http://www.wikidata.org/entity/') +
            Markup.escape(item_id) +
            Markup(r'" lang="') +
            Markup.escape(label['language']) +
            Markup(r'" data-entity-id="') +
            Markup.escape(item_id) +
            Markup(r'">') +
            Markup.escape(label['value']) +
            Markup(r'</a>'))

@app.template_filter()
def depicted_item_link(depicted):
    if 'item_id' in depicted:
        return item_link(depicted['item_id'], depicted['label'])
    else:
        return (Markup(r'<span class="wd-image-positions--snaktype-not-value" lang="') +
                Markup.escape(depicted['label']['language']) +
                Markup(r'">') +
                Markup.escape(depicted['label']['value']) +
                Markup(r'</span>'))

@app.template_global()
def authentication_area():
    if 'OAUTH' not in app.config:
        return Markup()

    session = authenticated_session('www.wikidata.org')
    if session is None:
        userinfo = None
    else:
        try:
            userinfo = session.get(action='query',
                                   meta='userinfo')['query']['userinfo']
        except mwapi.errors.APIError as e:
            if e.code == 'mwoauth-invalid-authorization':
                # e. g. consumer version updated, treat as not logged in
                flask.session.pop('oauth_access_token')
                userinfo = None
            else:
                raise e

    if userinfo is None:
        return (Markup(r'<a id="login" class="navbar-text" href="') +
                Markup.escape(flask.url_for('login')) +
                Markup(r'">Log in</a>'))

    csrf_token = flask.session.get('_csrf_token')
    if not csrf_token:
        csrf_token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
        flask.session['_csrf_token'] = csrf_token

    # prefix based on role, add user into user database if not logged in
    role = "Contributor "
    try:
        result = queries.query_db(queries.is_project_lead(), params=[userinfo['name']]) 
        if not result:
            # if not in userbase then add as contributor
            queries.query_db(queries.add_user(), params=[userinfo['name'], False, False])
        else:
            output = queries.jsonify_rows(result)[0]
            if output['is_project_lead']:
                role = "Project Lead "
    except Exception as ex:
        print(ex)
        return flask.jsonify(error=404, text=str(ex)), 404

    return (Markup(r'<span class="navbar-text">Logged in as ') +
            role + 
            user_link(userinfo['name']) +
            Markup(r'</span><span id="csrf_token" style="display: none;">') +
            Markup.escape(csrf_token) +
            Markup(r'</span>'))

@app.template_global()
def user_logged_in():
    return 'oauth_access_token' in flask.session

@app.template_global()
def project_lead_area():
    # only show this if someone is a project lead
    userinfo = get_userinfo()
    if userinfo:
        result = queries.query_db(queries.is_project_lead(), params=[userinfo['name']]) 
        if not result:
            # if not in userbase then add as contributor
            queries.query_db(queries.add_user(), params=[userinfo['name'], False, False])
        else:
            output = queries.jsonify_rows(result)[0]
            if output['is_project_lead']:
                return True
    return False
    
@app.errorhandler(WrongDataValueType)
def handle_wrong_data_value_type(error):
    response = flask.render_template('wrong-data-value-type.html',
                                     expected_data_value_type=error.expected_data_value_type,
                                     actual_data_value_type=error.actual_data_value_type)
    return response, error.status_code


def load_item_and_property(item_id, property_id,
                           include_depicteds=False, include_description=False, include_metadata=False, local_only=False, username=None):
    language_codes = request_language_codes()

    props = ['claims']
    if include_description:
        props.append('descriptions')

    session = anonymous_session('www.wikidata.org')
    api_response = session.get(action='wbgetentities',
                               props=props,
                               ids=item_id,
                               languages=language_codes)
    item_data = api_response['entities'][item_id]
    item = {
        'entity_id': item_id,
    }
    entity_ids = [item_id]

    if include_description:
        description = None
        for language_code in language_codes:
            if language_code in item_data['descriptions']:
                description = item_data['descriptions'][language_code]
                break
        item['description'] = description

    image_datavalue = best_value(item_data, property_id)
    if image_datavalue is not None:
        if image_datavalue['type'] != 'string':
            raise WrongDataValueType(expected_data_value_type='string', actual_data_value_type=image_datavalue['type'])
        image_title = image_datavalue['value']
        item.update(load_image(image_title, language_codes))

    if include_depicteds:
        if local_only and username:
            depicteds = []
            append_local_depicteds(depicteds, item_id, username)
        else:
            depicteds = depicted_items(item_data, item_id)
        for depicted in depicteds:
            if 'item_id' in depicted:
                entity_ids.append(depicted['item_id'])

    if include_metadata:
        metadata = entity_metadata(item_data)
        entity_ids += metadata.keys()

    labels = load_labels(entity_ids, language_codes)
    item['label'] = labels[item_id]

    if include_depicteds:
        for depicted in depicteds:
            depicted['label'] = depicted_label(depicted, labels, language_codes)
        item['depicteds'] = depicteds

    if include_metadata:
        item['metadata'] = []
        for property_id, values in metadata.items():
            for value in values:
                item['metadata'].append({
                    'label': labels[property_id],
                    'value': value
                })

    return item

def load_file(image_title):
    language_codes = request_language_codes()

    image = load_image(image_title, language_codes)
    if image is None:
        return None

    entity_id = 'M' + str(image['image_page_id'])
    file = {
        'entity_id': entity_id,
        **image,
    }
    entity_ids = []

    session = anonymous_session('commons.wikimedia.org')
    api_response = session.get(action='wbgetentities',
                               props=['claims'],
                               ids=[entity_id],
                               languages=language_codes)
    file_data = api_response['entities'][entity_id]

    depicteds = depicted_items(file_data, entity_id)
    for depicted in depicteds:
        if 'item_id' in depicted:
            entity_ids.append(depicted['item_id'])

    labels = load_labels(entity_ids, language_codes)

    for depicted in depicteds:
        depicted['label'] = depicted_label(depicted, labels, language_codes)
    file['depicteds'] = depicteds

    return file

def load_image(image_title, language_codes):
    """Load the metadata of an image file on Commons, without structured data."""
    session = anonymous_session('commons.wikimedia.org')

    query_params = query_default_params()
    query_params.setdefault('titles', set()).update(['File:' + image_title])
    image_attribution_query_add_params(query_params, image_title, language_codes[0])
    image_url_query_add_params(query_params, image_title)
    image_size_query_add_params(query_params, image_title)

    query_response = session.get(**query_params)
    page = query_response_page(query_response, 'File:' + image_title)
    if page.get('missing', False) or page.get('invalid', False):
        return None

    page_id = page['pageid']
    attribution = image_attribution_query_process_response(query_response, image_title, language_codes[0])
    url = image_url_query_process_response(query_response, image_title)
    width, height = image_size_query_process_response(query_response, image_title)
    return {
        'image_page_id': page_id,
        'image_title': image_title,
        'image_attribution': attribution,
        'image_url': url,
        'image_width': width,
        'image_height': height,
    }

def depicted_label(depicted, labels, language_codes):
    if 'item_id' in depicted:
        return labels[depicted['item_id']]
    elif depicted['snaktype'] == 'somevalue':
        return messages.somevalue(language_codes[0])
    elif depicted['snaktype'] == 'novalue':
        return messages.novalue(language_codes[0])
    else:
        raise ValueError('depicted has neither item ID nor somevalue/novalue snaktype')

def load_image_info(image_title):
    file_title = 'File:' + image_title.replace(' ', '_')
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(action='query', prop='imageinfo', iiprop='url|mime',
                           iiurlwidth=8000, titles=file_title)

    return response['query']['pages'][0]['imageinfo'][0]

def full_url(endpoint, **kwargs):
    return flask.url_for(endpoint, _external=True, _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'), **kwargs)

def current_url():
    return full_url(flask.request.endpoint, **flask.request.view_args)

def language_string_wikibase_to_iiif(language_string):
    if language_string is None:
        return None
    return {language_string['language']: language_string['value']}

def build_manifest(item):
    base_url = current_url()[:-len('/manifest.json')]
    fac = iiif_prezi.factory.ManifestFactory()
    fac.set_base_prezi_uri(base_url)
    fac.set_debug('error')

    iiif_item_label = language_string_wikibase_to_iiif(item['label'])
    iiif_item_description = language_string_wikibase_to_iiif(item['description'])

    manifest = fac.manifest(ident='manifest.json')
    if iiif_item_label is not None:
        manifest.label = iiif_item_label
    if iiif_item_description is not None:
        manifest.description = iiif_item_description
    attribution = image_attribution(item['image_title'], request_language_codes()[0])
    if attribution is not None:
        manifest.attribution = attribution['attribution_text']
        manifest.license = attribution['license_url']
    for metadata in item['metadata']:
        manifest.set_metadata({
            'label': language_string_wikibase_to_iiif(metadata['label']),
            'value': metadata['value'],
        })
    sequence = manifest.sequence(ident='normal', label='default order')
    canvas = sequence.canvas(ident='c0')
    if iiif_item_label is not None:
        canvas.label = iiif_item_label
    annolist = fac.annotationList(ident='annotations', label='Things depicted on this canvas')
    canvas.add_annotationList(annolist)
    populate_canvas(canvas, item, fac)

    return manifest

def populate_canvas(canvas, item, fac):
    image_info = load_image_info(item['image_title'])
    width, height = image_info['thumbwidth'], image_info['thumbheight']
    canvas.set_hw(height, width)
    anno = canvas.annotation(ident='a0')
    img = anno.image(ident=image_info['thumburl'], iiif=False)
    img.set_hw(height, width)
    img.format = image_info['mime']

    # add a thumbnail to the canvas
    thumbs_path = image_info['thumburl'].replace('/wikipedia/commons/', '/wikipedia/commons/thumb/')
    thumb_400 = thumbs_path + '/400px-' + item['image_title']
    canvas.thumbnail = fac.image(ident=thumb_400)
    canvas.thumbnail.format = image_info['mime']
    thumbwidth, thumbheight = 400, int(height * (400 / width))
    canvas.thumbnail.set_hw(thumbheight, thumbwidth)

def request_language_codes():
    """Determine the MediaWiki language codes to use from the request context."""
    # this could be made more accurate by using meta=languageinfo to match MediaWiki and BCP 47
    language_codes = flask.request.args.getlist('uselang')

    for accept_language in flask.request.headers.get('Accept-Language', '').split(','):
        language_code = accept_language.split(';')[0].strip()
        if language_code == '*' or not language_code:
            continue
        language_code = language_code.lower()
        if '-' in language_code:
            # these almost never match between MediaWiki and BCP 47:
            # https://gist.github.com/lucaswerkmeister/3469d5e7edbc59a8d03f347d35eed585
            language_codes.append(language_code.split('-')[0])
        else:
            # these often match between MediaWiki and BCP 47, just assume they do
            language_codes.append(language_code)

    language_codes.append('en')

    return language_codes

def best_value(entity_data, property_id):
    if property_id not in entity_data['claims']:
        return None

    statements = entity_data['claims'][property_id]
    normal_value = None
    deprecated_value = None

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            return datavalue
        if statement['rank'] == 'normal':
            normal_value = datavalue
        else:
            deprecated_value = datavalue

    return normal_value or deprecated_value

def best_values(entity_data, property_id):
    if property_id not in entity_data['claims']:
        return []

    statements = entity_data['claims'][property_id]
    preferred_values = []
    normal_values = []
    deprecated_values = []

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            preferred_values.append(datavalue)
        elif statement['rank'] == 'normal':
            normal_values.append(datavalue)
        else:
            deprecated_values.append(datavalue)

    return preferred_values or normal_values or deprecated_values

def depicted_items(entity_data, entity_id):
    depicteds = []

    statements = entity_data.get('claims', entity_data.get('statements', {}))
    if statements == []:
        statements = {}  # T222159
    for property_id in depicted_properties:
        for statement in statements.get(property_id, []):
            snaktype = statement['mainsnak']['snaktype']
            depicted = {
                'snaktype': snaktype,
                'statement_id': statement['id'],
                'property_id': property_id,
            }
            if snaktype == 'value':
                depicted['item_id'] = statement['mainsnak']['datavalue']['value']['id']

            for qualifier in statement.get('qualifiers', {}).get('P2677', []):
                if qualifier['snaktype'] != 'value':
                    continue
                depicted['iiif_region'] = qualifier['datavalue']['value']
                depicted['qualifier_hash'] = qualifier['hash']
                break

            depicteds.append(depicted)

    # user must be logged in to see their own personal annotations
    userinfo = get_userinfo()
    if userinfo:
        append_local_depicteds(depicteds, entity_id, userinfo['name'])

    return depicteds

def append_local_depicteds(depicteds, entity_id, username):
    # appends local depicted items to a passed in depicted list for a certain username + entity id
    result = queries.query_db(queries.get_object_statements(), params=[entity_id, username])
    output = queries.jsonify_rows(result)
    for property_id in depicted_properties:
        for row in output:
            depicted = {
                'snaktype': row['snaktype'],
                'statement_id': row['statement_id'],
                'property_id': property_id,
            }
            if row['snaktype'] == 'value':
                depicted['item_id'] = row['value_id']

            # check to see if there is qualifer info attached
            qualifier_result = queries.query_db(queries.get_qualifier_for_statement(), params=[row['statement_id']])
            qualifiers_output = queries.jsonify_rows(qualifier_result)
            if qualifiers_output:
                # only should be 1 qualifier for each statement
                qualifier = qualifiers_output[0]
                depicted['iiif_region'] = qualifier['iiif_region']
                depicted['qualifier_hash'] = qualifier['qualifier_hash']

            depicteds.append(depicted)

def entity_metadata(entity_data):
    # property IDs based on https://www.wikidata.org/wiki/Wikidata:WikiProject_Visual_arts/Item_structure#Describing_individual_objects
    property_ids = [
        'P170',  # creator
        'P1476',  # title
        'P571',  # inception
        'P186',  # material used
        'P2079',  # fabrication method
        'P2048',  # height
        'P2049',  # width
        'P2610',  # thickness
        'P88',  # commissioned by
        'P1071',  # location of final assembly
        'P127',  # owned by
        'P1259',  # coordinates of the point of view
        'P195',  # collection
        'P276',  # location
        'P635',  # coordinate location
        'P1684',  # inscription
        'P136',  # genre
        'P135',  # movement
        'P921',  # main subject
        'P144',  # based on
        'P941',  # inspired by
    ]
    metadata = collections.defaultdict(list)

    session = anonymous_session('www.wikidata.org')
    for property_id in property_ids:
        for value in best_values(entity_data, property_id):
            response = session.get(action='wbformatvalue',
                                   generate='text/html',
                                   datavalue=json.dumps(value),
                                   property=property_id)
            metadata[property_id].append(response['result'])

    return metadata

def load_labels(entity_ids, language_codes):
    entity_ids = list(set(entity_ids))
    labels = {}
    session = anonymous_session('www.wikidata.org')
    for chunk in [entity_ids[i:i + 50] for i in range(0, len(entity_ids), 50)]:
        items_data = session.get(action='wbgetentities', props='labels', languages=language_codes, ids=chunk)['entities']
        for entity_id, item_data in items_data.items():
            labels[entity_id] = {'language': 'zxx', 'value': entity_id}
            for language_code in language_codes:
                if language_code in item_data['labels']:
                    labels[entity_id] = item_data['labels'][language_code]
                    break
    return labels

def image_attribution(image_title, language_code):
    params = query_default_params()
    image_attribution_query_add_params(params, image_title, language_code)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_attribution_query_process_response(response, image_title, language_code)

def image_attribution_query_add_params(params, image_title, language_code):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['extmetadata'])
    params['iiextmetadatalanguage'] = language_code
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_attribution_query_process_response(response, image_title, language_code):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    metadata = imageinfo['extmetadata']
    no_value = {'value': None}

    attribution_required = metadata.get('AttributionRequired', no_value)['value']
    if attribution_required != 'true':
        return None

    attribution = Markup()

    artist = metadata.get('Artist', no_value)['value']
    if artist:
        attribution += Markup(r', ') + Markup(artist)

    license_short_name = metadata.get('LicenseShortName', no_value)['value']
    license_url = metadata.get('LicenseUrl', no_value)['value']
    if license_short_name and license_url:
        attribution += (Markup(r', <a href="') + Markup.escape(license_url) + Markup(r'">') +
                        Markup.escape(license_short_name) +
                        Markup(r'</a>'))

    credit = metadata.get('Credit', no_value)['value']
    if credit:
        attribution += Markup(r' (') + Markup(credit) + Markup(r')')

    attribution = attribution[len(', '):]

    return {
        'license_url': license_url,
        'attribution_text': attribution.striptags(),
        'attribution_html': attribution,
    }

def image_url(image_title):
    params = query_default_params()
    image_url_query_add_params(params, image_title)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_url_query_process_response(response, image_title)

def image_url_query_add_params(params, image_title):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['url'])
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_url_query_process_response(response, image_title):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    url = imageinfo['url']

    return url

def image_size(image_title):
    params = query_default_params()
    image_size_query_add_params(params, image_title)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_size_query_process_response(response, image_title)

def image_size_query_add_params(params, image_title):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['size'])
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_size_query_process_response(response, image_title):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    width = imageinfo['width']
    height = imageinfo['height']

    return width, height

def query_default_params():
    return {'action': 'query', 'formatversion': 2}

def query_response_page(response, title):
    """Get the page corresponding to a title from a query response."""
    for normalized in response['query'].get('normalized', []):
        if normalized['from'] == title:
            title = normalized['to']
            break
    pages = response['query']['pages']
    return next(page for page in pages if page['title'] == title)

def query_dashboard(page_number):
    """Returns list of object ids that should be displayed on the dashboard based on the page number"""
    query = '''SELECT DISTINCT ?item ?itemLabel WHERE {
                SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE]". }
                {
                    SELECT DISTINCT ?item WHERE {
                        ?item p:P31 ?statement0.
                        ?statement0 (ps:P31) wd:Q125191.
                        ?item p:P195 ?statement1.
                        ?statement1 (ps:P195/(wdt:P279*)) wd:Q1568434.
                        ?item p:P18 ?dummy0.
                    }
                    ORDER BY ASC(?item)
                    LIMIT %d
                    OFFSET %d
                }
            }''' % (ENTRIES_PER_PAGE, (page_number - 1) * ENTRIES_PER_PAGE) 

    query_results = requests_session.get('https://query.wikidata.org/sparql', params={'query': query}).json()

    # transform query results into just list of item ids
    dashboard_item_ids = []
    for item in query_results['results']['bindings']:
        dashboard_item_ids.append(item['itemLabel']['value'])
    return dashboard_item_ids

def get_userinfo():
    """Returns userinfo for currently logged in wikidata user, return None if no logged in user"""
    session = authenticated_session('www.wikidata.org')
    if session is None:
        userinfo = None
    else:
        try:
            userinfo = session.get(action='query',
                                   meta='userinfo')['query']['userinfo']
        except mwapi.errors.APIError as e:
            if e.code == 'mwoauth-invalid-authorization':
                # e. g. consumer version updated, treat as not logged in
                flask.session.pop('oauth_access_token')
                userinfo = None
            else:
                raise e

    return userinfo

def deny_access():
    userinfo = get_userinfo()
    if not userinfo:
        return True
    result = queries.query_db(queries.is_project_lead(), params=[userinfo['name']]) 
    if not result:
        # if not in userbase then add as contributor
        return True
    else:
        output = queries.jsonify_rows(result)[0]
        if output['is_project_lead'] == 0:
            return True
    return False

def upload_local_annotations(item_id, username):
    """Uploads all local statements/qualifiers to Wikidata for a given item_id/username pair"""
    result = queries.query_db(queries.get_object_statements(), params=[item_id, username])
    all_statements = queries.jsonify_rows(result)

    # set up wikidata api session
    session = authenticated_session("www.wikidata.org")
    if session is None:
        return 'Not logged in', 403

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']

    for statement in all_statements:
        value = json.dumps({'entity-type': 'item', 'id': statement['value_id']})
        try:
            response = session.post(action='wbcreateclaim',
                                    entity=statement['item_id'],
                                    snaktype=statement['snaktype'],
                                    property='P180',
                                    value=value,
                                    token=token)
        except mwapi.errors.APIError as error:
            return str(error), 500

        # check to see if the local statement has a qualifier and update if it does
        wikidata_statement_id = response['claim']['id']
        local_qualifier = queries.query_db(queries.get_qualifier_for_statement(), params=[statement['statement_id']])
        if local_qualifier:     
            jsonified_qualifier = queries.jsonify_rows(local_qualifier)[0]
            try:
                response = session.post(action='wbsetqualifier',
                                    claim=wikidata_statement_id,
                                    property='P2677',
                                    snaktype='value',
                                    value=('"' + jsonified_qualifier['iiif_region'] + '"'),
                                    **({'snakhash': jsonified_qualifier['qualifier_hash']} if jsonified_qualifier['qualifier_hash'] else {}),
                                    summary='region drawn manually using Dura Europos Wikidata Annotation Tool',
                                    token=token)
            except mwapi.errors.APIError as error:
                if error.code == 'no-such-qualifier':
                    return 'This region does not exist (anymore) – it may have been edited in the meantime. Please try reloading the page.', 500
                return str(error), 500
        
        # upload reference if needed
        if statement['reference_type'] and statement['reference_value']:
            # reference to be posted
            if statement['reference_type'] == 'P248':
                # stated in (reference to wikidata object)
                datavalue = {
                    'value': {
                        'entity-type':'item',
                        'id': statement['reference_value']
                    },
                    'type': 'wikibase-entityid'
                }
            else:
                # reference url
                datavalue = {
                    'value': statement['reference_value'],
                    'type': 'string',
                }

            snak_value = [{
                'snaktype': 'value',
                'property': statement['reference_type'],
                'datavalue': datavalue,
            }]

            if statement['reference_type'] == 'P248':
                snak_value[0]['datatype'] = 'wikibase-item'

            snak = {
                statement['reference_type']: snak_value
            }

            try:
                if statement['pages_value']:
                    page_datavalue = {
                        'value': statement['pages_value'],
                        'type': 'string'
                    }
                    page_snak_value = [{
                        'snaktype': 'value',
                        'property': 'P304',
                        'datavalue': page_datavalue,
                        'datatype': 'string' 
                    }]

                    snak['P304'] = page_snak_value
                    snak = json.dumps(snak)
                    snaks_order = ['P248', 'P304'] # if have page value guarenteed to be stated in
                    snaks_order = json.dumps(snaks_order)
                    
                    # have to mangle this in order to set snaks-order which has a hyphen
                    response = session.post(**{
                        'action': 'wbsetreference',
                        'statement': wikidata_statement_id,
                        'snaks': snak,
                        'snaks-order': snaks_order,
                        'token': token
                    })
                else:
                    snak = json.dumps(snak)
                    response = session.post(action='wbsetreference',
                                        statement=wikidata_statement_id,
                                        snaks=snak,
                                        token=token)
            except mwapi.errors.APIError as error:
                return str(error), 500
    return 'Success', 200

def delete_local_annotations(item_id, username):
    """Deletes all local statements/qualifiers for a given item_id/username pair"""
    # fetch all of the statements that need to be deleted
    result = queries.query_db(queries.get_object_statements(), params=[item_id, username])
    all_statements = queries.jsonify_rows(result)
    for statement in all_statements:
        # delete from the statements table
        queries.query_db(queries.delete_statement(), params=[statement['statement_id']])
        # delete from the qualifiers table -> if this statement doesn't have a qualifier then this will just do nothing
        queries.query_db(queries.delete_qualifier(), params=[statement['statement_id']])

def delete_all_comments_and_approval(item_id, username):
    """Deletes all comments and approvals associated with a give item_id/username pair"""
    queries.query_db(queries.delete_all_comments(), params=[item_id, username])
    queries.query_db(queries.delete_approval(), params=[username, item_id])

@app.after_request
def denyFrame(response):
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
