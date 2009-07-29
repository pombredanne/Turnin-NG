# Turnin-NG, an assignment submitter and manager. --- Project manager
# Copyright (C) 2009  Ryan Kavanagh <ryanakca@kubuntu.org>
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import os.path
import shutil
import subprocess
import tarfile

from turnin.configparser import ProjectCourse, ProjectProject
from turnin.sys import chown

def create_project(config_file, course, project):
    """
    Create the project 'project'.

    @type config_file: string
    @param config_file: path to the configuration file
    @type course: string
    @param course: course name
    @type project: string
    @param project project name
    @rtype: None

    """
    project_obj = ProjectProject(config_file, course, project)
    user = project_obj.course['user']
    group = project_obj.course['group']
    directory = project_obj.project['directory']
    os.makedirs(directory)
    os.chmod(directory, 0733)
    chown(directory, user, group)
    description = raw_input("[Optional] Project description: ")
    project_obj.write(True, description)

def delete_project(config_file, course, project):
    """
    Delete the project 'project'

    @type config_file: string
    @param config_file: path to the configuration file
    @type course: string
    @param course: course name
    @type project: string
    @param project: project name
    @rtype: None
    @raise ValueError: The user enters anything but 'YES' at the prompt.
    @raise valueError: The project doesn't exist.

    """
    if ProjectCourse(config_file, course).course.has_key(project):
        project_obj = ProjectProject(config_file, course, project)
        if raw_input("If you really want to delete this project and all " +
                "associated files, enter 'yes' in capital letters: ") == 'YES':
            shutil.rmtree(project_obj.project['directory'], ignore_errors=True)
            if project_obj.course['default'] == project:
                project_obj.course['default'] = ''
            del project_obj.course[project]
            project_obj.config.write()
        else:
            raise ValueError("Aborting and keeping project.")
    else:
        raise ValueError("%s is not an existing project in the course %s" %
                (project, course))

def compress_project(config_file, course, project):
    """
    Compress the project 'project'.

    @type config_file: string
    @param config_file: path to the configuration file
    @type course: string
    @param course: course name
    @type project: string
    @param project: project name
    @rtype: None
    @raise ValueError: The project is enabled / accepting submissions
    @raise ValueError: The project is already compressed
    @raise ValueError: The project doesn't exist.

    """
    if ProjectCourse(config_file, course).course.has_key(project):
        project_obj = ProjectProject(config_file, course, project)
        if project_obj.project['enabled']:
            raise ValueError("Project %s is enabled, please disable it first." %
                    project)
        # We need to check that it has a key before checking if it's Null or
        # not. If we skipped straight to checking if Null, and the key didn't
        # exist,  we would get a KeyError.
        elif (project_obj.project.has_key('tarball') and
                            project_obj.project['tarball']):
            raise ValueError("Project %s is already compressed." % project)
        archive_name = os.path.join(project_obj.course['directory'],
                project_obj.name + '.tar.gz')
        tar = tarfile.open(archive_name, 'w:gz')
        tar.add(project_obj.project['directory'], project_obj.name)
        tar.close() # This writes the tarball
        project_obj.project['tarball'] = archive_name
        project_obj.config.write()
        shutil.rmtree(project_obj.project['directory'], ignore_errors=True)
    else:
        raise ValueError("%s is not an existing project in the course %s" %
                (project, course))

def extract_project(config_file, course, project):
    """
    Uncompress the project 'project'.

    @type config_file: string
    @param config_file: path to the configuration file
    @type course: string
    @param course: course name
    @type project: string
    @param project: project name
    @rtype: None
    @raise ValueError: The project is not compressed
    @raise ValueError: The project does not exist.

    """
    if ProjectCourse(config_file, course).course.has_key(project):
        project_obj = ProjectProject(config_file, course, project)
        # We need to check that it has a key before checking if it's Null or
        # not. If we skipped straight to checking if Null, and the key didn't
        # exist,  we would get a KeyError.
        if (project_obj.project.has_key('tarball') and not
                                        project_obj.project['tarball']):
            raise ValueError("This project is not compressed.")
        print project_obj.project['tarball']
        tar = tarfile.open(project_obj.project['tarball'], 'r:gz')
        # Extract it to the course directory instead of to '.'
        tar.extractall(path=project_obj.course['directory'])
        tar.close()
        os.remove(project_obj.project['tarball'])
        project_obj.project['tarball'] = ''
        project_obj.config.write()
    else:
        raise ValueError("%s is not an existing project in the course %s" %
                (project, course))

def verify_sig(project_obj):
    """
    Verify the signatures of the projects with a signature.

    @type project_obj: ProjectProject
    @param project_obj: Project for which we'll verify the signatures
    @rtype: list
    @return: unsigned submissions
    @raise subprocess.CalledProcessError: gpg encounters an issue when verifying

    """
    # We need to sort so that we get ['archive.tar.gz', 'archive.tar.gz.sig']
    submissions = os.listdir(project_obj.project['directory'])
    if not submissions:
        raise ValueError("No assignments have been submitted yet.")
    signatures = []
    submissions.sort()
    for i, submission in enumerate(submissions):
        if submission.endswith('.sig'):
            signatures.append(submissions.pop(i)) # Signature file
            submissions.pop(i-1)                  # Archive
    for sig in signatures:
        print "Verifying %s" % sig[:-4]
        retcode = subprocess.call(['gpg', '--verify',
            os.path.join(project_obj.project['directory'], sig)])
        if retcode < 0:
            raise subprocess.CalledProcessError(retcode, ' '.join(cargs))
    ret = ['Unsigned submissions: ']
    if len(submissions) == 0:
        ret.append('None')
    else:
        ret += submissions
    return ret

def strip_random_suffix(project_obj):
    """
    Remove the 16 byte suffixes of the style username-XXXXXXXXXXXXXXXX.tar.gz

    @type project_obj: ProjectProject
    @param project_obj: Project for which we will strip the suffixes
    @raise ValueError: No assignments have been submitted.

    """
    submissions = os.listdir(project_obj.project['directory'])
    if not submissions:
        raise ValueError("No assignments have been submitted yet. Not " +
                "stripping suffixes")
    for submission in submissions:
        # Check that it's the right length before checking the format so that we
        # don't get string index out of range errors.
        if (len(submission) > 24) and (submission[-24] == '-') and \
                (submission[-7:] == '.tar.gz'):
            os.rename(
                os.path.join(project_obj.project['directory'], submission),
                os.path.join(project_obj.project['directory'],
                                submission[:-24] + '.tar.gz'))
        else:
            print ValueError("File %s does not have " % submission +
                    "the format username-XXXXXXXXXXXXXXXX.tar.gz, skipping.")
