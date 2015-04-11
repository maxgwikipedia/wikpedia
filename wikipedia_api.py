#!/usr/bin/python

"""

Author: Max Greenblatt

Purpose:
  1. Respond to code challenge given by Wikipedia

"""


import time
import os
from math import sqrt
from klein import Klein
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.static import File

app = Klein()
resource = app.resource

STATIC_FILE_RESOURCE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static_files')

# guid parts
ARTICLE_ID_LENGTH = 15
ARTICLE_VERSION_NUM_LENGTH = 10

# Article Edit Permission States
OPEN_EDITS = 1
QUEUED_EDITS = 2
LOCKED_EDITS = 3

class MockDatabase(object):

  def __init__(self):
    self.get = {}
    self.initialize_db()

  def initialize_db(self):

    # In a real DB for good housekeeping each table would have the following columns in addition to those listed: date_created, last_modified
    self.get = {
        'articles': [{'original_title': 'latest_plane_crash', 'id': 1}],
        'article_versions': [{'id': 1, 'article_id': 1, 'file_name': 'latest_plane_crash_2015040111430000000.html', 'timestamp':'2015040111430000000'}],
        'edit_article_permission_states': [{'id': OPEN_EDITS, 'state_name': 'open'}, {'id': QUEUED_EDITS, 'state_name': 'queuing'}, {'id': LOCKED_EDITS, 'state_name': 'locked'}],
        'edit_article_permissions': [{'id': 1, 'article_id': '1', 'permission_state': OPEN_EDITS, 'is_active': True}],
        'admin_users': [{'username': 'admin', 'password': 'password'}],  # Password would be hashed (and stronger) in real database, possibly use stronger form of authentication like TFA
        'edit_article_queue': []  # columns: id, article_id, original_version, revised_version_filename, timestamp
    }

  def save_article_version(self, id, article_id, file_name):
    new_version = dict(id=id, article_id=article_id, file_name=file_name)
    self.db['article_versions'].append(new_version)

MDB = MockDatabase()

def recursive_fib(n):

  try:
    n = int(n)
    if int(n) < 1:
      raise NotImplementedError("Fibonnacci values must be at least 1")

  except ValueError:
    raise NotImplementedError("Finbonacci values must be integers")

  if 1 <= n <= 2:
    return 1
  else:
    return recursive_fib(n-1) + recursive_fib(n-2)


def fast_fib(n):
    return ((1+sqrt(5))**n-(1-sqrt(5))**n)/(2**n*sqrt(5))


def get_latest_article_version():
  article_version = MDB.get['article_versions'][-1]

  guid = ('%0' + str(ARTICLE_ID_LENGTH) + 'd%0' + str(ARTICLE_VERSION_NUM_LENGTH) + 'd') % (article_version['article_id'], article_version['id'])

  return (guid, article_version['file_name'])


def breakdown_guid(guid):
  try:
    return (int(guid[:ARTICLE_ID_LENGTH]), int(guid[ARTICLE_ID_LENGTH:]))
  except ValueError:
    return (None, None)


def get_article_edit_permissions(article_id):
  """ Mock DB call to get an article's permissions """

  # This does a worst case scan of the 'table' a db would would make proper use of indices and bTrees, etc.
  for perm in MDB.get['edit_article_permissions']:
    if perm['id'] == article_id and perm['is_active']:
      return perm['permission_state']


def validate_user(username, password):
  """ Check authentication parameters """

  print username
  print password

  for user in MDB.get['admin_users']:

    if user['username'] == username and user['password'] == password:
      return True

  return False


def attempt_open_edit(article_id, version_num, request):
  """ When are article has open editing permissions try to update it """

  new_version = request.get('new_html', '')
  version_time = int(time.time()*1000)

  original_guid = ('%0' + str(ARTICLE_ID_LENGTH) + 'd%0' + str(ARTICLE_VERSION_NUM_LENGTH) + 'd') % (article_id, version_num)

  (latest_guid, filename) = get_latest_article_version()

  if original_guid != latest_guid:
    # Cannot update from an older version
    return "You are attempting to update from an old version of article: %s, the latest version is: %s" % (article_id, int(latest_guid[ARTICLE_ID_LENGTH:]))

  new_guid = ('%0' + str(ARTICLE_ID_LENGTH) + 'd%0' + str(ARTICLE_VERSION_NUM_LENGTH) + 'd') % (article_id, version_num+1)

  new_filename = '%s_%s.html' % (new_guid, version_time)

  with open(os.path.join(STATIC_FILE_RESOURCE_PATH, new_filename), 'w') as f:
    f.write(new_version)

  new_row = {'id': MDB.get['article_versions'][-1]['id']+1, 'article_id': article_id, 'file_name': new_filename, 'timestamp': version_time}
  MDB.get['article_versions'].append(new_row)


def add_edit_to_queue(article_id, version_num, request):
  raise NotImplementedError()


def perform_locked_edit(article_id, request):
  """ Locked Articles cannot be edited - tell the user this kindly :) """
  request.setResponseCode(200)
  john_oliver = 'https://en.wikipedia.org/wiki/Last_Week_Tonight_with_John_Oliver'
  returnValue("The requested article (%s) has been locked for editing. This is likely due to high-volume edits, a controversial topic, or John Oliver (%s) being awesome and influential!" % (article_id, john_oliver))


def update_article_permissions(article_id, permission):
  """ Deactivate current permission state and create a new one """
  # This is 'slow' given the lack of a database, but in a real DB saving old permission states would be smart to help with bookkeeping and being able ot trouble shoot problems in the future if 'rolling' back is possible

  # Validate the new permission state
  try:
    permission = int(permission)
    article_id = int(article_id)
  except ValueError:
    return False

  found_perm = False

  for state in MDB.get['edit_article_permission_states']:

    if state['id'] == int(permission):
      found_perm = True
      break

  if not found_perm:
    return False

  for idx in range(len(MDB.get['edit_article_permissions'])):
    if MDB.get['edit_article_permissions'][idx]['article_id'] == article_id:
       MDB.get['edit_article_permissions'][idx]['is_active'] = False

  new_row = {'id': MDB.get['edit_article_permissions'][-1]['id']+1, 'article_id': article_id, 'permission_state': permission, 'is_active': True}

  MDB.get['edit_article_permissions'].append(new_row)

  return True


@app.route('/Latest_plane_crash')
@inlineCallbacks
def latest_plane_crash(request):
  """ Endpoint for serving up our 'only' article """

  (guid, article_file_name) = get_latest_article_version()

  yield recursive_fib(34)  # Emulate overhead

  request.setHeader('article_guid', guid)

  returnValue(File(os.path.join(STATIC_FILE_RESOURCE_PATH, article_file_name)))


@app.route('/edit_article/<guid>', methods=['POST'])
def edit_article(request, guid):
  """ Endpoint to edit an article - must be a POST that contains new HTML text """

  if guid is None:
    request.setResponseCode(400)
    return 'Invalid Article Identifier'

  (article_id, version_num) = breakdown_guid(guid)

  if article_id is None or version_num is None:
    request.setResponseCode(400)
    return 'Invalid Article Identifier'

  edit_permission = get_article_edit_permissions(article_id)

  if edit_permission is OPEN_EDITS:
    return attempt_open_edit(article_id, version_num, request)

  elif edit_permission is QUEUED_EDITS:
    return add_edit_to_queue(article_id, version_num, request)

  elif edit_permission is LOCKED_EDITS:
    return perform_locked_edit(article_id, request)

  else:
    request.setResponseCode(400)
    return "ERROR: Article requested for edit is in an invalid state. Contact the administrator if this error message persists."


# Again, apologies for the abysmal security, but due to time constrains this was necessary - in the real world this would either be a proper user/pass auth schema, OAuth2, or a specialty api key
@app.route('/change_article_permissions/<article_id>/<permission>/<username>/<password>')
def change_article_permissions(request, article_id, permission, username, password):
  """ This endpoint allows qualified users to change the editing permissions of an article """

  print article_id, permission, username, password

  if not validate_user(username, password):
    request.setResponseCode(401)
    return "User is not authorized to access the requested resource."

  return "Article Permissions updated" if update_article_permissions(article_id, permission) else "There was a problem updating the permissions"


if __name__ == '__main__':
  app.debug = True
  app.run(host='0.0.0.0', port=8888)