# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# System Imports
import string, time, types, traceback, copy, pprint, sys, os, string
import linecache
import re
from cStringIO import StringIO

# Twisted Imports
from twisted.python import defer, rebuild, reflect, failure, log
from twisted.protocols import http

# Sibling Imports
import html, resource, error
from server import NOT_DONE_YET

"""A twisted web component framework.
"""

# magic value that sez a widget needs to take over the whole page.

FORGET_IT = 99

def listify(x):
    return [x]
def _ellipsize(x):
    y = repr(x)
    if len(y) > 1024:
        return y[:1024]+"..."
    return y

def htmlrepr(x):
    return htmlReprTypes.get(type(x), htmlUnknown)(x)

def htmlUnknown(x):
    return '<CODE>'+html.escape(repr(x))+'</code>'

def htmlDict(d):
    io = StringIO()
    w = io.write
    w('<table bgcolor="#cccc99"><tr><th colspan="2" align="left">Dictionary %d</th></tr>' % id(d))
    for k, v in d.items():
        if k == '__builtins__':
            v = 'builtin dictionary'
        w('\n<tr bgcolor="#ffff99"><td valign="top"><b>%s<b></td>\n<td>%s</td></tr>\n' % (htmlrepr(k), htmlrepr(v)))
    w('</table>')
    return io.getvalue()

def htmlList(l):
    io = StringIO()
    w = io.write
    w('<table bgcolor="#7777cc"><tr><th colspan="2" align="left">List %d</th></tr>' % id(l))
    for i in l:
        w('<tr bgcolor="#9999ff"><td>%s</td></tr>\n' % htmlrepr(i))
    w('</table>\n')
    return io.getvalue()

def htmlInst(i):
    if hasattr(i, "__html__"):
        s = i.__html__()
    else:
        s = '<CODE>'+html.escape(repr(i))+'</code>'
    return '''<table bgcolor="#cc7777"><tr><td><b>%s</b> instance</td></tr>
              <tr bgcolor="#ff9999"><td>%s</td></tr>
              </table>
              ''' % (i.__class__, s)

def htmlString(s):
    return html.escape(repr(s))

htmlReprTypes = {types.DictType: htmlDict,
                 types.ListType: htmlList,
                 types.InstanceType: htmlInst,
                 types.StringType: htmlString}

def formatFailure(myFailure):
    if not isinstance(myFailure, failure.Failure):
        return html.PRE(str(myFailure))
    io = StringIO()
    w = io.write
    w("<table>")
    w('<th align="left" colspan="3"><font color="red">%s: %s</font></th>' % (myFailure.type, myFailure.value))
    line = 0
    for method, filename, lineno, localVars, globalVars in myFailure.frames:
        # Cheat to make tracebacks shorter.
        if filename == '<string>':
            continue
        # file, line number
        w('<tr bgcolor="#%s"><td colspan="2" valign="top">%s, line %s in <b>%s</b><br><table width="100%%">' % (["bbbbbb", "cccccc"][line % 2], filename, lineno, method))
        snippet = ''
        for snipLineNo in range(lineno-2, lineno+2):
            snipLine = linecache.getline(filename, snipLineNo)
            snippet = snippet + snipLine
            snipLine = string.replace(
                string.replace(html.escape(string.rstrip(snipLine)),
                               '  ','&nbsp;'),
                '\t', '&nbsp; &nbsp; &nbsp; &nbsp; ')


            if snipLineNo == lineno:
                color = 'bgcolor="#ffffff"'
            else:
                color = ''
            w('<tr %s><td>%s</td><td><code>%s</code></td></tr>' % (color, snipLineNo,snipLine))
        w('</table></td></tr>')
        w('<tr bgcolor="#%s">' % (["bbbbbb", "cccccc"][line % 2]))
        # local vars
        for nm, varList in ('Locals', localVars), ('Globals', globalVars):
            w('<td valign="top"><table><tr><th align="left" colspan="2">'
              '%s'
              '</th></tr>' % nm)
            for name, var in varList:
                if re.search(r'\W'+name+r'\W', snippet):
                    w('<tr><td valign="top"><b>%s</b></td>'
                      '<td>%s</td></tr>' % (name, htmlrepr(var)))
            w('</table></td>')
        w('</td>')
        w('</tr>')
        line = line + 1
    return io.getvalue()

class Widget:
    """A component of a web page.
    """
    title = None
    def getTitle(self, request):
        return self.title or str(self.__class__)

    def display(self, request):
        """Implement me to represent your widget.

        I must return a list of strings and twisted.python.defer.Deferred
        instances.
        """
        raise NotImplementedError("%s.display" % str(self.__class__))

class StreamWidget(Widget):
    """A 'streamable' component of a webpage.
    """

    def stream(self, write, request):
        """Call 'write' multiple times with a string argument to represent this widget.
        """
        raise NotImplementedError("%s.stream" % self.__class__)

    def display(self, request):
        """Produce a list containing a single string.
        """
        l = []
        try:
            result = self.stream(l.append, request)
            if result is not None:
                return result
            return l
        except:
            return [formatFailure(failure.Failure())]

class WidgetMixin(Widget):
    """A mix-in wrapper for a Widget.

    This mixin can be used to wrap functionality in any other widget with a
    method of your choosing.  It is designed to be used for mix-in classes that
    can be mixed in to Form, StreamWidget, Presentation, etc, to augment the
    data available to the 'display' methods of those classes, usually by adding
    it to a Session.
    """

    def display(self):
        raise NotImplementedError("%s.display" % self.__class__)

    def displayMixedWidget(self, request):
        for base in reflect.allYourBase(self.__class__):
            if issubclass(base, Widget) and not issubclass(base, WidgetMixin):
                return base.display(self, request)

class Presentation(Widget):
    """I am a widget which formats a template with interspersed python expressions.
    """
    template = '''
    Hello, %%%%world%%%%.
    '''
    world = "you didn't assign to the 'template' attribute"
    def __init__(self, template=None, filename=None):
        if filename:
            self.template = open(filename).read()
        elif template:
            self.template = template
        self.variables = {}
        self.tmpl = string.split(self.template, "%%%%")

    def addClassVars(self, namespace, Class):
        for base in Class.__bases__:
            # Traverse only superclasses that know about Presentation.
            if issubclass(base, Presentation) and base is not Presentation:
                self.addClassVars(namespace, base)
        # 'lower' classes in the class heirarchy take precedence.
        for k in Class.__dict__.keys():
            namespace[k] = getattr(self, k)

    def addVariables(self, namespace, request):
        self.addClassVars(namespace, self.__class__)

    def prePresent(self, request):
        """Perform any tasks which must be done before presenting the page.
        """

    def formatTraceback(self, tb):
        return [html.PRE(tb)]

    def streamCall(self, call, *args, **kw):
        """Utility: Call a method like StreamWidget's 'stream'.
        """
        io = StringIO()
        apply(call, (io.write,) + args, kw)
        return io.getvalue()

    def display(self, request):
        tm = []
        flip = 0
        namespace = {}
        self.prePresent(request)
        self.addVariables(namespace, request)
        # This variable may not be obscured...
        namespace['request'] = request
        namespace['self'] = self
        for elem in self.tmpl:
            flip = not flip
            if flip:
                if elem:
                    tm.append(elem)
            else:
                try:
                    x = eval(elem, namespace, namespace)
                except:
                    io = StringIO()
                    log.deferr()
                    tm.append(formatFailure(failure.Failure()))
                else:
                    if isinstance(x, types.ListType):
                        tm.extend(x)
                    elif isinstance(x, Widget):
                        val = x.display(request)
                        if not isinstance(val, types.ListType):
                            raise Exception("%s.display did not return a list, it returned %s!" % (x.__class__, repr(val)))
                        tm.extend(val)
                    else:
                        # Only two allowed types here should be deferred and
                        # string.
                        tm.append(x)
        return tm


def htmlFor_hidden(write, name, value):
    write('<INPUT TYPE="hidden" NAME="%s" VALUE="%s">' % (name, value))

def htmlFor_file(write, name, value):
    write('<INPUT SIZE=60 TYPE="file" NAME="%s">' % name)

def htmlFor_string(write, name, value):
    write('<INPUT SIZE=60 TYPE="text" NAME="%s" VALUE="%s">' % (name, value))

def htmlFor_password(write, name, value):
    write('<INPUT SIZE=60 TYPE="password" NAME=%s>' % name)

def htmlFor_text(write, name, value):
    write('<TEXTAREA COLS="60" ROWS="10" NAME="%s" WRAP="virtual">%s</textarea>' % (name, value))

def htmlFor_menu(write, name, value):
    "Value of the format [(optionName, displayName), ...]"
    write('  <SELECT NAME="%s">\n' % name)
    for optionName, displayName in value:
        write('    <OPTION VALUE="%s">%s</option>\n' % (optionName, displayName))
    if not value:
        write('    <OPTION VALUE=""></option>\n')
    write("  </select>\n")

def htmlFor_checkbox(write, name, value):
    "A checkbox."
    if value:
        value = 'checked'
    else:
        value = ''
    write('<INPUT TYPE="checkbox" NAME="__checkboxes__" VALUE="%s" %s>\n' % (name, value))

def htmlFor_checkgroup(write, name, value):
    "A check-group."
    for optionName, displayName, checked in value:
        checked = (checked and 'checked') or ''
        write('<INPUT TYPE="checkbox" NAME="%s" VALUE="%s" %s>%s<br>\n' % (name, optionName, checked, displayName))

class FormInputError(Exception):
    pass

class Form(StreamWidget):
    """I am a web form.

    In order to use me, you probably want to set self.formFields (or override
    'getFormFields') and override 'process'.  In order to demonstrate how this
    is done, here is a small sample Form subclass::

      |  from twisted.web import widgets
      |  class HelloForm(widgets.Form):
      |      formFields = [
      |          ['string', 'Who to greet?', 'whoToGreet', 'World',
      |            'This is for choosing who to greet.'],
      |          ['menu', 'How to greet?', 'how', [('cheerfully', 'with a smile'),
      |                                            ('sullenly', 'without enthusiasm'),
      |                                            ('spontaneously', 'on the spur of the moment')]]
      |            'This is for choosing how to greet them.']
      |      def process(self, write, request, submit, whoToGreet, how):
      |          write('The web wakes up and %s says, \"Hello, %s!\"' % (how, whoToGreet))

    If you load this widget, you will see that it displays a form with 2 inputs
    derived from data in formFields.  Note the argument names to 'process':
    after 'write' and 'request', they are the same as the 3rd elements ('Input
    Name' parameters) of the formFields list.
    """

    formGen = {
        'hidden': htmlFor_hidden,
        'file': htmlFor_file,
        'string': htmlFor_string,
        'int': htmlFor_string,
        'text': htmlFor_text,
        'menu': htmlFor_menu,
        'password': htmlFor_password,
        'checkbox': htmlFor_checkbox,
        'checkgroup': htmlFor_checkgroup
    }

    formParse = {
        'int': int
    }

    formFields = [
    ]

    def getFormFields(self, request, fieldSet = None):
        """I return a list of lists describing this form.

        This information is used both to display the form and to process it.
        The list is in the following format::

          | [['Input Type',   'Display Name',   'Input Name',   'Input Value', 'Description'],
          |  ['Input Type 2', 'Display Name 2', 'Input Name 2', 'Input Value 2', 'Description 2']
          |  ...]

        Valid values for 'Input Type' are:

          * 'hidden': a hidden field that contains a string that the user won't change

          * 'string': a short string

          * 'int': an integer

          * 'text': a longer text field, suitable for entering paragraphs

          * 'menu': an HTML SELECT input, a list of choices

          * 'checkgroup': a group of checkboxes

          * 'password': a 'string' field where the contents are not visible as the user types

          * 'file': a file-upload form (EXPERIMENTAL)

        'Display Name' is a descriptive string that will be used to
        identify the field to the user.

        The 'Input Name' must be a legal Python identifier that describes both
        the value's name on the HTML form and the name of an argument to
        'self.process()'.

        The 'Input Value' is usually a string, but its value can depend on the
        'Input Type'.  'int' it is an integer, 'menu' it is a list of pairs of
        strings, representing (value, name) pairs for the menu options.  Input
        value for 'checkgroup' should be a list of ('inputName', 'Display
        Name', 'checked') triplets.

        The 'Description' field is an (optional) string which describes the form
        item to the user.

        If this result is statically determined for your Form subclass, you can
        assign it to FormSubclass.formFields; if you need to determine it
        dynamically, you can override this method.

        Note: In many cases it is desirable to use user input for defaults in
        the form rather than those supplied by your calculations, which is what
        this method will do to self.formFields.  If this is the case for you,
        but you still need to dynamically calculate some fields, pass your
        results back through this method by doing::

          |  def getFormFields(self, request):
          |      myFormFields = [self.myFieldCalculator()]
          |      return widgets.Form.getFormFields(self, request, myFormFields)

        """
        fields = []
        if fieldSet is None:
            fieldSet = self.formFields
        if not self.shouldProcess(request):
            return fieldSet

        for field in fieldSet:
            if len(field)==5:
                inputType, displayName, inputName, inputValue, description = field
            else:
                inputType, displayName, inputName, inputValue = field
                description = ""

            if inputType == 'checkbox':
                if request.args.has_key('__checkboxes__'):
                    if inputName in request.args['__checkboxes__']:
                        inputValue = 1
                    else:
                        inputValue = 0
                else:
                    inputValue = 0
            elif inputType == 'checkgroup':
                if request.args.has_key(inputName):
                    keys = request.args[inputName]
                else:
                    keys = []
                iv = inputValue
                inputValue = []
                for optionName, optionDisplayName, checked in iv:
                    checked = optionName in keys
                    inputValue.append([optionName, optionDisplayName, checked])
            elif request.args.has_key(inputName):
                iv = request.args[inputName][0]
                if inputType == 'menu':
                    if iv in inputValue:
                        inputValue.remove(iv)
                        inputValue.insert(0, iv)
                else:
                    inputValue = iv
            fields.append([inputType, displayName, inputName, inputValue, description])
        return fields

    submitNames = ['Submit']
    actionURI = ''

    def format(self, form, write, request):
        """I display an HTML FORM according to the result of self.getFormFields.
        """
        write('<FORM ENCTYPE="multipart/form-data" METHOD="post" ACTION="%s">\n'
              '<TABLE BORDER="0">\n' % (self.actionURI or request.uri))
  
        for field in form:
            if len(field) == 5:
                inputType, displayName, inputName, inputValue, description = field
            else:
                inputType, displayName, inputName, inputValue = field
                description = ""
            write('<TR>\n<TD ALIGN="right" VALIGN="top"><B>%s</b></td>\n'
                  '<TD VALIGN="%s">\n' %
                  (displayName, ((inputType == 'text') and 'top') or 'middle'))
            self.formGen[inputType](write, inputName, inputValue)
            write('\n<br>\n<font size="-1">%s</font></td>\n</tr>\n' % description)

                 

        write('<TR><TD></TD><TD ALIGN="left"><hr>\n')
        for submitName in self.submitNames:
            write('<INPUT TYPE="submit" NAME="submit" VALUE="%s">\n' % submitName)
        write('</td></tr>\n</table>\n'
              '<INPUT TYPE="hidden" NAME="__formtype__" VALUE="%s">\n'
              % (str(self.__class__)))
        fid = self.getFormID()
        if fid:
            write('<INPUT TYPE="hidden" NAME="__formid__" VALUE="%s">\n' % fid)
        write("</form>\n")

    def getFormID(self):
        """Override me: I disambiguate between multiple forms of the same type.

        In order to determine which form an HTTP POST request is for, you must
        have some unique identifier which distinguishes your form from other
        forms of the same class.  An example of such a unique identifier would
        be: on a page with multiple FrobConf forms, each FrobConf form refers
        to a particular Frobnitz instance, which has a unique id().  The
        FrobConf form's getFormID would probably look like this::

          |  def getFormID(self):
          |      return str(id(self.frobnitz))

        By default, this method will return None, since distinct Form instances
        may be identical as far as the application is concerned.
        """

    def process(self, write, request, submit, **kw):
        """Override me: I process a form.

        I will only be called when the correct form input data to process this
        form has been received.

        I take a variable number of arguments, beginning with 'write',
        'request', and 'submit'.  'write' is a callable object that will append
        a string to the response, 'request' is a twisted.web.request.Request
        instance, and 'submit' is the name of the submit action taken.

        The remainder of my arguments must be correctly named.  They will each be named after one of the

        """
        write("Submit: %s <br> %s" % (submit, html.PRE(pprint.PrettyPrinter().pformat(kw))))

    def _doProcess(self, form, write, request):
        """(internal) Prepare arguments for self.process.
        """
        args = copy.copy(request.args)
        kw = {}
        for field in form:
            inputType, displayName, inputName, inputValue = field[:4]
            if inputType == 'checkbox':
                if request.args.has_key('__checkboxes__'):
                    if inputName in request.args['__checkboxes__']:
                        formData = 1
                    else:
                        formData = 0
                else:
                    formData = 0
            elif inputType == 'checkgroup':
                if args.has_key(inputName):
                    formData = args[inputName]
                    del args[inputName]
                else:
                    formData = []
            else:
                if not args.has_key(inputName):
                    raise FormInputError("missing field %s." % repr(inputName))
                formData = args[inputName]
                del args[inputName]
                if not len(formData) == 1:
                    raise FormInputError("multiple values for field %s." %repr(inputName))
                formData = formData[0]
                method = self.formParse.get(inputType)
                if method:
                    formData = method(formData)
            kw[inputName] = formData
        submitAction = args.get('submit')
        if submitAction:
            submitAction = submitAction[0]
        for field in ['submit', '__formtype__', '__checkboxes__']:
            if args.has_key(field):
                del args[field]
        if args:
            raise FormInputError("unknown fields: %s" % repr(args))
        return apply(self.process, (write, request, submitAction), kw)

    def formatError(self,error):
        """Format an error message.

        By default, this will make the message appear in red, bold italics.
        """
        return '<FONT COLOR=RED><B><I>%s</i></b></font><br>\n' % error

    def shouldProcess(self, request):
        args = request.args
        fid = self.getFormID()
        return (args and # there are arguments to the request
                args.has_key('__formtype__') and # this is a widgets.Form request
                args['__formtype__'][0] == str(self.__class__) and # it is for a form of my type
                ((not fid) or # I am only allowed one form per page
                 (args.has_key('__formid__') and # if I distinguish myself from others, the request must too
                  args['__formid__'][0] == fid))) # I am in fact the same

    def tryAgain(self, err, req):
        """Utility method for re-drawing the form with an error message.

        This is handy in forms that process Deferred results.  Normally you can
        just raise a FormInputError() and this will happen by default.

        """
        l = []
        w = l.append
        w(self.formatError(err))
        self.format(self.getFormFields(req), w, req)
        return l

    def stream(self, write, request):
        """Render the results of displaying or processing the form.
        """
        args = request.args
        form = self.getFormFields(request)
        if self.shouldProcess(request):
            try:
                return self._doProcess(form, write, request)
            except FormInputError, fie:
                write(self.formatError(str(fie)))
        return self.format(form, write, request)


class DataWidget(Widget):
    def __init__(self, data):
        self.data = data
    def display(self, request):
        return [self.data]

class Time(Widget):
    def display(self, request):
        return [time.ctime(time.time())]

class Container(Widget):
    def __init__(self, *widgets):
        self.widgets = widgets

    def display(self, request):
        value = []
        for widget in self.widgets:
            d = widget.display(request)
            value.extend(d)
        return value

class _RequestDeferral:
    def __init__(self):
        self.deferred = defer.Deferred()
        self.io = StringIO()
        self.write = self.io.write

    def finish(self):
        self.deferred.callback([self.io.getvalue()])

def possiblyDeferWidget(widget, request):
    # web in my head get it out get it out
    try:
        disp = widget.display(request)
        # if this widget wants to defer anything -- well, I guess we've got to
        # defer it.
        for elem in disp:
            if isinstance(elem, defer.Deferred):
                req = _RequestDeferral()
                RenderSession(disp, req)
                return req.deferred
        return string.join(disp, '')
    except:
        io = StringIO()
        traceback.print_exc(file=io)
        return html.PRE(io.getvalue())

class RenderSession:
    """I handle rendering of a list of deferreds, outputting their
    results in correct order."""

    class Sentinel:
        pass
    
    def __init__(self, lst, request):
        self.lst = lst
        self.request = request
        self.needsHeaders = 0
        self.beforeBody = 1
        self.forgotten = 0
        toArm = []
        for i in range(len(self.lst)):
            item = self.lst[i]
            if isinstance(item, defer.Deferred):
                self.lst[i] = (self._addDeferred(item), item)
                toArm.append(item)

        self.keepRendering()
        for item in toArm:
            item.arm()

    def _addDeferred(self, deferred):
        sentinel = self.Sentinel()
        if hasattr(deferred, 'needsHeader'):
            # You might want to set a header from a deferred, in which
            # case you have to set an attribute -- needsHeader.
            self.needsHeaders = self.needsHeaders + 1
            args = (sentinel, 1)
        else:
            args = (sentinel, 0)
        deferred.addCallbacks(self.callback, self.callback,
                              callbackArgs=args, errbackArgs=args)
        return sentinel

    def callback(self, result, sentinel, decNeedsHeaders):
        if self.forgotten:
            return
        if result != FORGET_IT:
            self.needsHeaders = self.needsHeaders - decNeedsHeaders
        else:
            result = [FORGET_IT]

        # Make sure result is a sequence,
        if not type(result) in (types.ListType, types.TupleType):
            result = [result]

        # If the deferred does not wish to produce it's result all at
        # once, it can give us a partial result as
        #  (NOT_DONE_YET, partial_result)
        ## XXX: How would a deferred go about producing the result in multiple
        ## stages?? --glyph
        if result[0] is NOT_DONE_YET:
            done = 0
            result = result[1]
            if not type(result) in (types.ListType, types.TupleType):
                result = [result]
        else:
            done = 1

        toArm = []
        for i in xrange(len(result)):
            item = result[i]
            if isinstance(item, defer.Deferred):
                result[i] = (self._addDeferred(item), item)
                toArm.append(item)

        for position in range(len(self.lst)):
            item = self.lst[position]
            if type(item) is types.TupleType and len(item) > 0:
                if item[0] is sentinel:
                    break
        else:
            raise 'Sentinel for Deferred not found!'

        if done:
            self.lst[position:position+1] = result
        else:
            self.lst[position:position] = result

        # Consolidate strings to minimize length of list,
        # Good try, but this seems really buggy
##        for i in range(1, len(self.lst)):
##            last = type(self.lst[i-1]) is types.StringType
##            this = type(self.lst[i]) is types.StringType
##            if last and this:
##                self.lst[i-1:i+1] = [self.lst[i-1] + self.lst[i]]

        self.keepRendering()
        for r in toArm:
            r.arm()


    def keepRendering(self):
        if self.needsHeaders:
            # short circuit actual rendering process until we're sure no
            # more deferreds need to set headers...
            return

        assert self.lst is not None, "This shouldn't happen."
        while 1:
            item = self.lst[0]
            if self.beforeBody and FORGET_IT in self.lst:
                # If I haven't moved yet, and the widget wants to take
                # over the page, let it do so!
                self.forgotten = 1
                return

            if isinstance(item, types.StringType):
                self.beforeBody = 0
                self.request.write(item)
            elif type(item) is types.TupleType and len(item) > 0:
                if isinstance(item[0], self.Sentinel):
                    return
            elif isinstance(item, failure.Failure):
                self.request.write(formatFailure(item))
            else:
                self.beforeBody = 0
                unknown = html.PRE(repr(item))
                self.request.write("RENDERING UNKNOWN: %s" % unknown)

            del self.lst[0]
            if len(self.lst) == 0:
                self.lst = None
                self.request.finish()
                return


## XXX: is this needed?
class WidgetResource(resource.Resource):
    def __init__(self, widget):
        self.widget = widget

    def render(self, request):
        RenderSession(self.widget.display(request), request)
        return NOT_DONE_YET


class Page(resource.Resource, Presentation):

    def __init__(self):
        resource.Resource.__init__(self)
        Presentation.__init__(self)

    def render(self, request):
        displayed = self.display(request)
        RenderSession(displayed, request)
        return NOT_DONE_YET


class WidgetPage(Page):
    """
    I am a Page that takes a Widget in its constructor, and displays that
    Widget wrapped up in a simple HTML template.
    """
    stylesheet = '''
    A
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        color: #336699;
        text-decoration: none;
    }

    TH
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        font-weight: bold;
        text-decoration: none;
    }

    PRE, CODE
    {
        font-family: Courier New, Courier;
    }

    P, BODY, TD, OL, UL, MENU, BLOCKQUOTE, DIV
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        color: #000000;
    }
    '''

    template = '''<html>
    <style>
    %%%%self.stylesheet%%%%
    </style>
    <head>
    <title>%%%%self.title%%%%</title>
    <base href="%%%%request.prePathURL()%%%%">
    </head>
    <body>
    <h1>%%%%self.title%%%%</h1>
    %%%%self.widget%%%%
    </body>
    </html>
    '''

    title = 'No Title'
    widget = 'No Widget'

    def __init__(self, widget):
        Page.__init__(self)
        self.widget = widget
        if hasattr(widget, 'stylesheet'):
            self.stylesheet = widget.stylesheet

    def prePresent(self, request):
        self.title = self.widget.getTitle(request)

    def render(self, request):
        displayed = self.display(request)
        RenderSession(displayed, request)
        return NOT_DONE_YET

class Gadget(resource.Resource):
    """I am a collection of Widgets, to be rendered through a Page Factory.
    self.pageFactory should be a Resource that takes a Widget in its
    constructor. The default is twisted.web.widgets.WidgetPage.
    """

    isLeaf = 0

    def __init__(self):
        resource.Resource.__init__(self)
        self.widgets = {}
        self.files = []
        self.modules = []
        self.paths = {}

    def render(self, request):
        #Redirect to view this entity as a collection.
        request.setResponseCode(http.TEMPORARY_REDIRECT)
        request.setHeader("location","http://%s%s/" % (
            request.getHeader("host"),
            (string.split(request.uri,'?')[0])))
        return "NO DICE!"

    def putWidget(self, path, widget):
        """
        Gadget.putWidget(path, widget)
        Add a Widget to this Gadget. It will be rendered through the
        pageFactory associated with this Gadget, whenever 'path' is requested.
        """
        self.widgets[path] = widget

    #this is an obsolete function
    def addFile(self, path):
        """
        Gadget.addFile(path)
        Add a static path to this Gadget. This method is obsolete, use
        Gadget.putPath instead.
        """
        
        print "Gadget.addFile() is deprecated."
        self.paths[path] = path

    def putPath(self, path, pathname):
        """
        Gadget.putPath(path, pathname)
        Add a static path to this Gadget. Whenever 'path' is requested,
        twisted.web.static.File(pathname) is sent.
        """
        self.paths[path] = pathname

    def getWidget(self, path, request):
        return self.widgets.get(path)

    def pageFactory(self, *args, **kwargs):
        """
        Gadget.pageFactory(*args, **kwargs) -> Resource
        By default, this method returns self.page(*args, **kwargs). It
        is only for backwards-compatibility -- you should set the 'pageFactory'
        attribute on your Gadget inside of its __init__ method.
        """
        #XXX: delete this after a while.
        if hasattr(self, "page"):
            print "Gadget.page is deprecated, use Gadget.pageFactory instead"
            return apply(self.page, args, kwargs)
        else:
            return apply(WidgetPage, args, kwargs)

    def getChild(self, path, request):
        if path == '':
            # ZOOP!
            if isinstance(self, Widget):
                return self.pageFactory(self)
        widget = self.getWidget(path, request)
        if widget:
            if isinstance(widget, resource.Resource):
                return widget
            else:
                p = self.pageFactory(widget)
                p.isLeaf = getattr(widget,'isLeaf',0)
                return p
        elif self.paths.has_key(path):
            prefix = getattr(sys.modules[self.__module__], '__file__', '')
            if prefix:
                prefix = os.path.abspath(os.path.dirname(prefix))
            return static.File(os.path.join(prefix, self.paths[path]))
        
        elif path == '__reload__':
            return self.pageFactory(Reloader(map(reflect.namedModule, [self.__module__] + self.modules)))
        else:
            return error.NoResource()


class TitleBox(Presentation):

    template = '''\
<table %%%%self.widthOption%%%% cellpadding="1" cellspacing="0" border="0"><tr>\
<td bgcolor="%%%%self.borderColor%%%%"><center><font color="%%%%self.titleTextColor%%%%">%%%%self.title%%%%</font></center>\
<table width="100%" cellpadding="3" cellspacing="0" border="0"><tr>\
<td bgcolor="%%%%self.boxColor%%%%"><font color="%%%%self.boxTextColor%%%%">%%%%self.widget%%%%</font></td>\
</tr></table></td></tr></table>\
'''

    borderColor = '#000000'
    titleTextColor = '#ffffff'
    boxTextColor = '#000000'
    boxColor = '#ffffff'
    widthOption = 'width="100%"'

    title = 'No Title'
    widget = 'No Widget'

    def __init__(self, title, widget):
        """Wrap a widget with a given title.
        """
        self.widget = widget
        self.title = title
        Presentation.__init__(self)


class Reloader(Presentation):
    template = '''
    Reloading...
    <ul>
    %%%%reload(request)%%%%
    </ul> ... reloaded!
    '''
    def __init__(self, modules):
        Presentation.__init__(self)
        self.modules = modules

    def reload(self, request):
        request.setHeader("location", "..")
        request.setResponseCode(http.TEMPORARY_REDIRECT)
        x = []
        write = x.append
        for module in self.modules:
            rebuild.rebuild(module)
            write('<li>reloaded %s<br>' % module.__name__)
        return x

class Sidebar(StreamWidget):
    bar = [
        ['Twisted',
            ['mirror', 'http://coopweb.org/ssd/twisted/'],
            ['mailing list', 'cgi-bin/mailman/listinfo/twisted-python']
        ]
    ]

    headingColor = 'ffffff'
    headingTextColor = '000000'
    activeHeadingColor = '000000'
    activeHeadingTextColor = 'ffffff'
    sectionColor = '000088'
    sectionTextColor = '008888'
    activeSectionColor = '0000ff'
    activeSectionTextColor = '00ffff'

    def __init__(self, highlightHeading, highlightSection):
        self.highlightHeading = highlightHeading
        self.highlightSection = highlightSection

    def getList(self):
        return self.bar

    def stream(self, write, request):
        write("<TABLE width=120 cellspacing=1 cellpadding=1 border=0>")
        for each in self.getList():
            if each[0] == self.highlightHeading:
                headingColor = self.activeHeadingColor
                headingTextColor = self.activeHeadingTextColor
                canHighlight = 1
            else:
                headingColor = self.headingColor
                headingTextColor = self.headingTextColor
                canHighlight = 0
            write('<TR><TD colspan=2 bgcolor="#%s"><FONT COLOR="%s"><b>%s</b>'
                  '</font></td></td></tr>\n' % (headingColor, headingTextColor, each[0]))
            for name, link in each[1:]:
                if canHighlight and (name == self.highlightSection):
                    sectionColor = self.activeSectionColor
                    sectionTextColor = self.activeSectionTextColor
                else:
                    sectionColor = self.sectionColor
                    sectionTextColor = self.sectionTextColor
                write('<TR><td align=right bgcolor="#%s" width=6>-</td>'
                      '<TD bgcolor="#%s"><A HREF="%s"><FONT COLOR="#%s">%s'
                      '</font></a></td></tr>'
                       % (sectionColor, sectionColor, request.sibLink(link), sectionTextColor, name))
        write("</table>")

import static
