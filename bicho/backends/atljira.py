# -*- coding: utf-8 -*-
# Copyright (C) 2007-2013 GSyC/LibreSoft, Universidad Rey Juan Carlos
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Authors: Daniel Izquierdo Cortazar <dizquierdo@gsyc.es>
#          Juan Francisco Gato Luis <jfcogato@libresoft.es>
#          Luis Cañas Díaz <lcanas@bitergia.com>
#          Santiago Dueñas <sduenas@libresoft.es>
#          Alvaro del Castillo <acs@bitergia.com>

import datetime
import urllib
import time
import sys

from storm.locals import Int, DateTime, Unicode, Reference, Desc

from dateutil.parser import parse
from bicho.common import Issue, People, Tracker, Comment, Change, Attachment
from bicho.backends import Backend
from bicho.db.database import DBIssue, DBBackend, DBTracker, get_database
from bicho.config import Config
from bicho.utils import printout, printerr, printdbg

from jira.client import JIRA

import feedparser



class DBJiraIssueExt(object):
    """
    """
    __storm_table__ = 'issues_ext_jira'

    id = Int(primary=True)
    issue_key = Unicode()
    link = Unicode()
    title = Unicode()
    environment = Unicode()
    security = Unicode()
    updated = DateTime()
    version = Unicode()
    component = Unicode()
    votes = Int()
    project = Unicode()
    project_id = Int
    project_key = Unicode()
    status = Unicode()
    resolution = Unicode()

    issue_id = Int()

    issue = Reference(issue_id, DBIssue.id)

    def __init__(self, issue_id):
        self.issue_id = issue_id


class DBJiraIssueExtMySQL(DBJiraIssueExt):
    """
    MySQL subclass of L{DBJiraIssueExt}
    """

    __sql_table__ = 'CREATE TABLE IF NOT EXISTS issues_ext_jira ( \
                     id INTEGER NOT NULL AUTO_INCREMENT, \
                     issue_key VARCHAR(32) NOT NULL, \
                     link VARCHAR(100) NOT NULL, \
                     title VARCHAR(100) NOT NULL, \
                     environment VARCHAR(35) NOT NULL, \
                     security VARCHAR(35) NOT NULL, \
                     updated DATETIME NOT NULL, \
                     version VARCHAR(35) NOT NULL, \
                     component VARCHAR(35) NOT NULL, \
                     votes INTEGER UNSIGNED, \
                     project VARCHAR(35) NOT NULL, \
                     project_id INTEGER UNSIGNED, \
                     project_key VARCHAR(35) NOT NULL, \
                     status  VARCHAR(35) NOT NULL, \
                     resolution VARCHAR(35) NOT NULL, \
                     issue_id INTEGER NOT NULL, \
                     PRIMARY KEY(id), \
                     UNIQUE KEY(issue_id), \
                     INDEX ext_issue_idx(issue_id), \
                     FOREIGN KEY(issue_id) \
                       REFERENCES issues (id) \
                         ON DELETE CASCADE \
                         ON UPDATE CASCADE \
                     ) ENGINE=MYISAM;'


class DBJiraBackend(DBBackend):
    """
    Adapter for Jira backend.
    """
    def __init__(self):
        self.MYSQL_EXT = [DBJiraIssueExtMySQL]

    def insert_issue_ext(self, store, issue, issue_id):
        """
        Insert the given extra parameters of issue with id X{issue_id}.

        @param store: database connection
        @type store: L{storm.locals.Store}
        @param issue: issue to insert
        @type issue: L{JiraIssue}
        @param issue_id: identifier of the issue
        @type issue_id: C{int}

        @return: the inserted extra parameters issue
        @rtype: L{DBJiraIssueExt}
        """

        newIssue = False

        try:
            db_issue_ext = store.find(DBJiraIssueExt,
                                      DBJiraIssueExt.issue_id == issue_id).one()
            if not db_issue_ext:
                newIssue = True
                db_issue_ext = DBJiraIssueExt(issue_id)

            db_issue_ext.title = self.__return_unicode(issue.title)
            db_issue_ext.issue_key = self.__return_unicode(issue.issue_key)
            db_issue_ext.link = self.__return_unicode(issue.link)
            db_issue_ext.environment = self.__return_unicode(issue.environment)
            db_issue_ext.security = self.__return_unicode(issue.security)
            db_issue_ext.updated = issue.updated
            db_issue_ext.version = self.__return_unicode(issue.version)
            db_issue_ext.component = self.__return_unicode(issue.component)
            db_issue_ext.votes = issue.votes
            db_issue_ext.project = self.__return_unicode(issue.project)
            db_issue_ext.project_id = issue.project_id
            db_issue_ext.project_key = self.__return_unicode(issue.project_key)
            db_issue_ext.status = self.__return_unicode(issue.status)
            db_issue_ext.resolution = self.__return_unicode(issue.resolution)

            if newIssue is True:
                store.add(db_issue_ext)

            store.flush()
            return db_issue_ext
        except:
            store.rollback()
            raise

    def __return_unicode(self, str):
        """
        Decodes string and pays attention to empty ones
        """
        if str:
            return unicode(str)
        else:
            return unicode('')

    def insert_comment_ext(self, store, comment, comment_id):
        """
        Does nothing
        """
        pass

    def insert_attachment_ext(self, store, attch, attch_id):
        """
        Does nothing
        """
        pass

    def insert_change_ext(self, store, change, change_id):
        """
        Does nothing
        """
        pass

    def get_last_modification_date(self, store, tracker_id):
        # get last modification date (day) stored in the database
        # select date_last_updated as date from issues_ext_bugzilla order by date
        result = store.find(DBJiraIssueExt,
                            DBJiraIssueExt.issue_id == DBIssue.id,
                            DBIssue.tracker_id == DBTracker.id,
                            DBTracker.id == tracker_id)

        if result.is_empty():
            return None
        else:
            db_issue_ext = result.order_by(Desc(DBJiraIssueExt.updated))[0]
            return db_issue_ext.updated.strftime('%Y-%m-%d %H:%M')

####################################


class JiraIssue(Issue):
    """
    Ad-hoc Issue extensions for jira's issue
    """
    def __init__(self, issue, type, summary, description, submitted_by, submitted_on):
        Issue.__init__(self, issue, type, summary, description, submitted_by, submitted_on)

        self.title = None
        self.issue_key = None
        self.link = None
        self.environment = None
        self.security = None
        self.updated = None
        self.version = None
        self.component = None
        self.votes = None
        self.project = None
        self.project_id = None
        self.project_key = None
        self.status = None
        self.resolution = None

    def setStatus(self, status):
        self.status = status

    def setResolution(self, resolution):
        self.resolution = resolution

    def setTitle(self, title):
        self.title = title

    def setIssue_key(self, issue_key):
        self.issue_key = issue_key

    def setLink(self, link):
        self.link = link

    def setEnvironment(self, environment):
        self.environment = environment

    def setSecurity(self, security):
        self.security = security

    def setUpdated(self, updated):
        self.updated = updated

    def setVersion(self, version):
        self.version = version

    def setComponent(self, component):
        self.component = component

    def setVotes(self, votes):
        self.votes = votes

    def setProject(self, project):
        self.project = project

    def setProject_id(self, project_id):
        self.project_id = project_id

    def setProject_key(self, project_key):
        self.project_key = project_key


class JiraComment():
    def __init__(self):
        self.comment = None
        self.comment_id = None
        self.comment_author = None
        self.comment_created = None


class JiraAttachment():
    def __init__(self):
        self.attachment_id = None
        self.attachment_name = None
        self.attachment_size = None
        self.attachment_author = None
        self.attachment_created = None


class Customfield():
    def __init__(self):
        self.customfield_id = None
        self.customfield_key = None
        self.customfieldname = None
        self.customfieldvalue = None


class Bug():

    def __init__(self):
        self.title = None
        self.link = None
        self.description = ""
        self.environment = None
        self.summary = None
        self.bug_type = None
        self.status = None
        self.resolution = None
        self.security = None
        self.created = None
        self.updated = None
        self.version = None
        self.component = None
        self.votes = None
        self.project = None
        self.project_id = None
        self.project_key = None
        self.issue_key = None
        self.key_id = None
        self.assignee = None
        self.assignee_username = None
        self.reporter = None
        self.reporter_username = None

        self.comments = []
        self.attachments = []
        self.customfields = []


class BugsHandler():

    def __init__(self):
        self.issues_data = []
        self.init_bug()

    def init_bug(self):

        self.mapping = []
        self.comments = []
        self.attachments = []
        self.customfields = []

        self.title = None
        self.link = None
        self.description = ""
        self.environment = ""
        self.summary = None
        self.bug_type = None
        self.status = None
        self.resolution = None
        self.security = None
        self.created = None
        self.updated = None
        self.version = None
        self.component = None
        self.votes = None

        self.project = None
        self.project_id = None
        self.project_key = None
        self.issue_key = None
        self.key_id = None
        self.assignee = None
        self.assignee_username = None
        self.reporter = None
        self.reporter_username = None
        self.comment = unicode("")
        self.comment_id = None
        self.comment_author = None
        self.comment_created = None
        self.attachment_id = None
        self.attachment_name = None
        self.attachment_size = None
        self.attachment_author = None
        self.attachment_created = None
        self.customfield_id = None
        self.customfield_key = None
        self.customfieldname = None
        self.customfieldvalue = None

        #control data
        self.first_desc = True
        self.is_title = False
        self.is_link = False
        self.is_description = False
        self.is_environment = False
        self.is_summary = False
        self.is_bug_type = False
        self.is_status = False
        self.is_resolution = False
        self.is_security = False
        self.is_created = False
        self.is_updated = False
        self.is_version = False
        self.is_component = False
        self.is_votes = False

        self.is_project = False
        self.is_issue_key = False
        self.is_assignee = False
        self.is_reporter = False
        self.is_comment = False
        self.is_customfieldname = False
        self.is_customfieldvalue = False

    def startElement(self, name, attrs):
        if name == "item":
            self.init_bug()
        elif name == 'title':
            self.is_title = True
        elif name == 'link':
            self.is_link = True
            self.link = ''
        elif name == 'description':
            self.is_description = True
        elif name == 'environment':
            self.is_environment = True
        elif name == 'summary':
            self.is_summary = True
        elif name == 'type':
            self.is_bug_type = True
        elif name == 'status':
            self.is_status = True
        elif name == 'resolution':
            self.is_resolution = True
        elif name == 'security':
            self.is_security = True
        elif name == 'created':
            self.is_created = True
            self.created = ''
        elif name == 'updated':
            self.is_updated = True
            self.updated = ''
        elif name == 'version':
            self.is_version = True
        elif name == 'component':
            self.is_component = True
        elif name == 'votes':
            self.is_votes = True
        elif name == 'project':
            self.is_project = True
            self.project_id = attrs['id']
            self.project_key = attrs['key']
        elif name == 'key':
            self.is_issue_key = True
            self.key_id = attrs['id']
        elif name == 'assignee':
            self.is_assignee = True
            self.assignee_username = attrs['username']
        elif name == 'reporter':
            self.is_reporter = True
            self.reporter_username = attrs['username']
        elif name == 'comment':
            self.is_comment = True
            self.comment_id = attrs['id']
            self.comment_author = attrs['author']
            self.comment_created = attrs['created']
        elif name == 'attachment':
            #no data in characters
            self.attachment_id = attrs['id']
            self.attachment_name = attrs['name']
            self.attachment_size = attrs['size']
            self.attachment_author = attrs['author']
            self.attachment_created = attrs['created']
        elif name == 'customfield':
            self.customfield_id = attrs['id']
            self.customfield_key = attrs['key']
        elif name == 'customfieldname':
            self.is_customfieldname = True
        elif name == 'customfieldvalues':
            self.is_customfieldvalue = True


    def characters(self, ch):
        if self.is_title:
            self.title = ch
        elif self.is_link:
            self.link += ch
        elif self.is_description:
            #FIXME problems with ascii, not support str() function
            if (self.first_desc is True):
                self.first_desc = False
            else:
                self.description = self.description + ch.strip()
        elif self.is_environment:
            self.environment = self.environment + ch
        elif self.is_summary:
            self.summary = ch
        elif self.is_bug_type:
            self.bug_type = ch
        elif self.is_status:
            self.status = ch
        elif self.is_resolution:
            self.resolution = ch
        elif self.is_security:
            self.security = ch
        elif self.is_assignee:
            #FIXME problems with ascii, not support str() function
            self.assignee = ch
        elif self.is_reporter:
            #FIXME problems with ascii, not support str() function
            self.reporter = ch
        elif self.is_created:
            self.created += ch
        elif self.is_updated:
            self.updated += ch
        elif self.is_version:
            self.version = ch
        elif self.is_component:
            self.component = ch
        elif self.is_votes:
            self.votes = int(ch)
        elif self.is_project:
            self.project = ch
        elif self.is_issue_key:
            self.issue_key = ch
        elif self.is_comment:
            #FIXME problems with ascii, not support str() function
            self.comment = self.comment + ch
        elif self.is_customfieldname:
            self.customfieldname = ch
        elif self.is_customfieldvalue:
            if ch.lstrip().__len__() != 0:
                self.customfieldvalue = ch.lstrip()


    def endElement(self, name):
        if name == 'title':
            self.is_title = False
        elif name == 'link':
            self.is_link = False
        elif name == 'project':
            self.is_project = False
        elif name == 'description':
            self.is_description = False
        elif name == 'environment':
            self.is_environment = False
        elif name == 'key':
            self.is_issue_key = False
        elif name == 'summary':
            self.is_summary = False
        elif name == 'type':
            self.is_bug_type = False
        elif name == 'status':
            self.is_status = False
        elif name == 'resolution':
            self.is_resolution = False
        elif name == 'security':
            self.is_security = False
        elif name == 'assignee':
            self.is_assignee = False
        elif name == 'reporter':
            self.is_reporter = False
        elif name == 'created':
            self.is_created = False
        elif name == 'updated':
            self.is_updated = False
        elif name == 'version':
            self.is_version = False
        elif name == 'component':
            self.is_component = False
        elif name == 'votes':
            self.is_votes = False
        elif name == 'comment':
            self.is_comment = False
            newComment = JiraComment()
            newComment.comment = self.comment
            newComment.comment_id = self.comment_id
            newComment.comment_author = self.comment_author
            newComment.comment_created = self.comment_created
            self.comments.append(newComment)
            self.comment = ""

        elif name == 'attachment':
            newAttachment = JiraAttachment()
            newAttachment.attachment_id = self.attachment_id
            newAttachment.attachment_name = self.attachment_name
            newAttachment.attachment_size = self.attachment_size
            newAttachment.attachment_author = self.attachment_author
            newAttachment.attachment_created = self.attachment_created
            self.attachments.append(newAttachment)

        elif name == 'customfieldname':
            self.is_customfieldname = False
        elif name == 'customfieldvalues':
            self.is_customfieldvalue = False

        elif name == 'customfield':
            newCustomfield = Customfield()
            newCustomfield.customfield_id = self.customfield_id
            newCustomfield.customfield_Key = self.customfield_key
            newCustomfield.customfieldname = self.customfieldname
            newCustomfield.customfieldvalue = self.customfieldvalue
            self.customfields.append(newCustomfield)

        elif name == 'item':
            newbug = Bug()
            newbug.title = self.title
            newbug.link = self.link
            newbug.description = self.description
            newbug.environment = self.environment
            newbug.summary = self.summary
            newbug.bug_type = self.bug_type
            newbug.status = self.status
            newbug.resolution = self.resolution
            newbug.security = self.security
            newbug.created = self.created
            newbug.updated = self.updated
            newbug.version = self.version
            newbug.component = self.component
            newbug.votes = self.votes
            newbug.project = self.project
            newbug.project_id = self.project_id
            newbug.project_key = self.project_key
            newbug.issue_key = self.issue_key
            newbug.key_id = self.key_id
            newbug.assignee = self.assignee
            newbug.assignee_username = self.assignee_username
            newbug.reporter = self.reporter
            newbug.reporter_username = self.reporter_username
            newbug.comments = self.comments
            newbug.attachments = self.attachments
            newbug.customfields = self.customfields

            self.issues_data.append(newbug)

    @staticmethod
    def remove_unicode(str):
        """
        Cleanup u'' chars indicating a unicode string
        """
        if (str.startswith('u\'') and str.endswith('\'')):
            str = str[2:len(str) - 1]
        return str

    def obtainDataPerson(self, obj):
        person = People(obj.name)
        if hasattr(obj, 'displayName'):
            person.set_name(obj.displayName)
        if hasattr(obj, 'emailAddress'):
            person.set_email(obj.emailAddress)
        return person

    def createPerson(self, obj, attr):
        person = People(None)
        if (attr == 'assignee'):
            if (hasattr(obj, 'assignee') and (obj.assignee != None)):
                person = self.obtainDataPerson(obj.assignee)
        elif (attr == 'reporter'):
            if (hasattr(obj, 'reporter') and (obj.reporter != None)):
                person = self.obtainDataPerson(obj.reporter)
        elif ((attr == 'changeAuthor') or (attr == 'commentAuthor') or (attr == 'attachmentAuthor')):
            if (hasattr(obj, 'author') and (obj.author != None)):
                person = self.obtainDataPerson(obj.author)
        return person


    def concatenateItems(self, items):
        itemsResult = (items.pop(0)).name
        for item in items:
            itemsResult += ', ' + item.name
        return itemsResult
        

    def getIssues(self, issues, url):
        bicho_bugs = []
        for bug in issues:
            bicho_bugs.append(self.getIssue(bug, url))
        return bicho_bugs

    def getIssue(self, bug, url):
        #Return the data bug from JIRA REST API into issue object
        issue_id = bug.id
        issue_type = bug.fields.issuetype
        summary = bug.fields.summary
        description = bug.fields.description
        status = bug.fields.status.name
        resolution = bug.fields.resolution

        assigned_by = self.createPerson(bug.fields, 'assignee')

        submitted_by = self.createPerson(bug.fields, 'reporter')
        submitted_on = parse(bug.fields.created).replace(tzinfo=None)

        issue = JiraIssue(issue_id, issue_type, summary, description, submitted_by, submitted_on)
        issue.set_assigned(assigned_by)
        issue.setIssue_key(bug.key)
        issue.setTitle("[" + bug.key + "] " + summary)
        issue.setLink(url+bug.key)
        issue.setEnvironment(bug.fields.environment)
        issue.setSecurity("")
        issue.setUpdated(parse(bug.fields.updated).replace(tzinfo=None))
        if (bug.fields.versions):
            issue.setVersion(self.concatenateItems(bug.fields.versions))
        if (bug.fields.components):
            issue.setComponent(self.concatenateItems(bug.fields.components))
        issue.setVotes(bug.fields.votes.votes)
        issue.setProject(bug.fields.project.name)
        issue.setProject_id(bug.fields.project.id)
        issue.setProject_key(bug.fields.project.key)
        issue.setStatus(status)
        issue.setResolution(resolution)

        if hasattr(bug, 'changelog'):
            for history in bug.changelog.histories:
                for item in history.items:
                    field = item.field
                    old = item.fromString
                    new = item.toString
                    author = self.createPerson(history,'changeAuthor')
                    date = parse(history.created).replace(tzinfo=None)
                    change = Change(field, old, new, author, date)
                    issue.add_change(change) 

        if hasattr(bug.fields, 'comment'):
            for comment in bug.fields.comment.comments:
                comment_by = self.createPerson(comment, 'commentAuthor')
                comment_on = parse(comment.created).replace(tzinfo=None)
                com = Comment(comment.body, comment_by, comment_on)
                issue.add_comment(com)

        if hasattr(bug.fields, 'attachment'):
            for attachment in bug.fields.attachment:
                url = attachment.content
                attachment_by = self.createPerson(attachment, 'attachmentAuthor')
                attachment_on = parse(attachment.created).replace(tzinfo=None)
                attach = Attachment(url, attachment_by, attachment_on)
                issue.add_attachment(attach)
        #FIXME customfield are not stored in db because is the fields has the same in all the bugs

        return issue


class JiraBackend(Backend):
    """
Jira Backend
"""

    def __init__(self):
        self.delay = Config.delay
        self.url = Config.url
        self.serverUrl = Config.url.split("/browse/")[0]
        self.projectName = Config.url.split("/browse/")[1]

    def basic_jira_url(self):
        serverUrl = self.url.split("/browse/")[0]
        product = self.url.split("/browse/")[1]
        query = "/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml"
        url_issues = serverUrl + query + "?pid=" + product
        url_issues += "&sorter/field=updated&sorter/order=INC"
        if self.last_mod_date:
            url_issues += "&updated:after=" + self.last_mod_date
        return url_issues


    def bugsNumber(self, jira):
        printdbg("Getting number of issues: " + self.url)
        issue = jira.search_issues('project=' + self.projectName,startAt=0,maxResults=1)
        bugs = issue.total
        return int(bugs)

    # http://stackoverflow.com/questions/8733233/filtering-out-certain-bytes-in-python
    def valid_XML_char_ordinal(self, i):
        return ( # conditions ordered by presumed frequency
            0x20 <= i <= 0xD7FF
            or i in (0x9, 0xA, 0xD)
            or 0xE000 <= i <= 0xFFFD
            or 0x10000 <= i <= 0x10FFFF)

    def analyze_bug_list(self, issues, url, bugsdb, dbtrk_id):
        handler = BugsHandler()

        try:
            issuesDB = handler.getIssues(issues, url)
            for issue in issuesDB:
                bugsdb.insert_issue(issue, dbtrk_id)
        except Exception, e:
            import traceback
            traceback.print_exc()
            sys.exit(0)

    def run(self):
        printout("Running Bicho with delay of %s seconds" % (str(self.delay)))

        issues_per_query = 100
        
        bugsdb = get_database(DBJiraBackend())

        bugsdb.insert_supported_traker("jira", "4.1.2")
        trk = Tracker(self.url.split("-")[0], "jira", "4.1.2")
        dbtrk = bugsdb.insert_tracker(trk)

        serverUrl = self.url.split("/browse/")[0]
        query = "/si/jira.issueviews:issue-xml/"
        project = self.url.split("/browse/")[1]

        options_jira = {
            'server': self.serverUrl
        }
        
        jira = JIRA(options_jira)

        if (project.split("-").__len__() > 1):
            bug_key = project
            project = project.split("-")[0]
            bugs_number = self.bugsNumber(jira)

            try:
                issue = jira.issue(bug_key,expand='changelog')
                self.analyze_bug_list(issue, self.serverUrl+'/browse/', bugsdb, dbtrk.id)
            except Exception, e:
                #printerr(e)
                print(e)

        else:
            self.last_mod_date = bugsdb.get_last_modification_date(tracker_id=dbtrk.id)
            if self.last_mod_date:
                # self.url = self.url + "&updated:after=" + last_mod_date
                printdbg("Last bugs cached were modified at: %s" % self.last_mod_date)

            bugs_number = self.bugsNumber(jira)
            print "Tickets to be retrieved:", str(bugs_number)
            remaining = bugs_number
            while (remaining > 0):
                startAtIssue = bugs_number-remaining
                jira = JIRA(options_jira)
                issuesAux = jira.search_issues('project=' + self.projectName + ' order by id asc',startAt=startAtIssue,maxResults=issues_per_query,fields=None)
                issues=[]
                for i in issuesAux:
                    issues.append(jira.issue(i.key, expand='changelog'))
                self.analyze_bug_list(issues, self.serverUrl+'/browse/', bugsdb, dbtrk.id)
                remaining -= issues_per_query
                #print "Remaining time: ", (remaining/issues_per_xml_query)*Config.delay/60, "m", "(",remaining,")"
                time.sleep(self.delay)

            printout("Done. %s bugs analyzed" % (bugs_number))

Backend.register_backend("atljira", JiraBackend)
