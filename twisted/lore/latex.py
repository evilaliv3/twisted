# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 

from twisted.web import microdom, domhelpers
import os, re
from cStringIO import StringIO

escapingRE = re.compile(r'([#$%&_{}^~])')
lowerUpperRE = re.compile(r'([a-z])([A-Z])')

def latexEscape(text):
    text = escapingRE.sub(r'\\\1{}', text.replace('\\', '$\\backslash$'))
    return text.replace('\n', ' ')

entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"',
             'copy': '\\copyright'}

def getLatexText(node, writer, filter=lambda x:x):
    if isinstance(node, microdom.EntityReference):
        writer(entities.get(node.data, ''))
        return
    if hasattr(node, 'data'):
        writer(filter(node.data))
    for child in node.childNodes :
        getLatexText(child, writer, filter)


class LatexSpitter:


    ignoring = 0
    normalizing = 1
    escaping = 1
    baseLevel = 0
    raw = 0
    hyphenateCode = 0

    def __init__(self, writer, currDir='.', filename=''):
        self.writer = writer
        self.currDir = currDir
        self.filename = filename

    def visitNode(self, node):
        if not hasattr(node, 'tagName'):
            getLatexText(node, self.writer, latexEscape)
            return
        m = getattr(self, 'visitNode_'+node.tagName, self.visitNodeDefault)
        m(node)

    def visitNodeDefault(self, node):
        s = getattr(self, 'mapStart_'+node.tagName, None)
        if s:
            self.writer(s)
        for child in node.childNodes:
            self.visitNode(child)
        s = getattr(self, 'mapEnd_'+node.tagName, None)
        if s:
            self.writer(s)

    def visitNode_pre(self, node):
        self.writer('\\begin{verbatim}\n')
        getLatexText(node, self.writer, lambda x:x)
        self.writer('\\end{verbatim}\n')

    def visitNode_code(self, node):
        fout = StringIO()
        getLatexText(node, fout.write, latexEscape)
        data = fout.getvalue()
        olddata = data
        data = lowerUpperRE.sub(r'\1\\textrm{\\-}\2', data)
        if data == olddata:
            # No hyphenation points were added, so fall back to adding
            # hyphenation points at dots (except not for leading dots)
            data = data[:1] + data[1:].replace('.', '.\\textrm{\\-}')
        self.writer('\\texttt{'+data+'}')

    def visitNode_img(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('src'))
        target, ext = os.path.splitext(fileName)
        ext = ext[1:]
        m = getattr(self, 'convert_'+ext, None)
        if not m:
            return
        target = os.path.join(self.currDir, os.path.basename(target)+'.eps')
        m(fileName, target)
        target = os.path.basename(target)
        self.writer('\\includegraphics{%s}\n' % target)

    def convert_png(self, src, target):
        os.system("pngtopnm %s | pnmtops > %s" % (src, target))

    def visitNodeHeader(self, node):
        level = int(node.tagName[1])-2
        level += self.baseLevel
        self.writer('\n\n\\'+level*'sub'+'section{')
        self.visitNodeDefault(node)
        self.writer('}\n')

    def visitNode_h1(self, node):
        pass

    def visitNode_a(self, node):
        if node.hasAttribute('class'):
            if node.getAttribute('class').endswith('listing'):
                return self.visitNode_a_listing(node)
        if node.hasAttribute('href'):
            return self.visitNode_a_href(node)
        if node.hasAttribute('name'):
            return self.visitNode_a_name(node)
        self.visitNodeDefault(node)

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('\\begin{verbatim}')
        self.writer(open(fileName).read())
        self.writer('\\end{verbatim}')
        # Write a caption for this source listing
        self.writer('\\begin{center}\\raisebox{1ex}[1ex]{Source listing for '
                    '\\begin{em}%s\\end{em}}\\end{center}' 
                    % latexEscape(fileName))

    def visitNode_a_href(self, node):
        self.visitNodeDefault(node)
        href = node.getAttribute('href')
        ref = None
        if href.startswith('#'):
            ref = self.filename + 'HASH' + href[1:]
        elif href.find('#') != 1 and not href.startswith('http:'):
            ref = href.replace('#', 'HASH')
        elif not href.startswith('http:'):
            ref = href
        if ref:
            self.writer(' (page \\pageref{%s})' % ref)

    def visitNode_a_name(self, node):
        self.writer('\\label{%sHASH%s}' % (self.filename,
                                           node.getAttribute('name')))
        self.visitNodeDefault(node)

    def visitNode_style(self, node):
        pass

    def visitNode_span(self, node):
        if not node.hasAttribute('class'):
            return self.visitNodeDefault(node)
        node.tagName += '_'+node.getAttribute('class')
        self.visitNode(node)

    visitNode_div = visitNode_span

    visitNode_h2 = visitNode_3 = visitNode_h4 = visitNodeHeader

    mapStart_title = '\\title{'
    mapEnd_title = '}\n'

    mapStart_html = '\\documentclass{article}\n'
    mapStart_body = '\\begin{document}\n\\maketitle\n'
    mapEnd_body = '\\end{document}'

    mapStart_dl = mapStart_ul = '\\begin{itemize}\n'
    mapEnd_dl = mapEnd_ul = '\\end{itemize}\n'

    mapStart_ol = '\\begin{enumerate}\n'
    mapEnd_ol = '\\end{enumerate}\n'

    mapStart_li = '\\item '
    mapEnd_li = '\n'

    mapStart_dt = '\\item{'
    mapEnd_dt = '}'
    mapEnd_dd = '\n'

    mapStart_p = '\n\n'

    mapStart_strong = mapStart_em = '\\begin{em}'
    mapEnd_strong = mapEnd_em = '\\end{em}'

    mapStart_q = "``"
    mapEnd_q = "''"

    mapStart_span_footnote = '\\footnote{'
    mapEnd_span_footnote = '}'

    mapStart_div_note = '\\begin{quotation}\\textbf{Note:}'
    mapEnd_div_note = '\\end{quotation}'


class SectionLatexSpitter(LatexSpitter):

    baseLevel = 1

    def visitNode_title(self, node):
        self.writer('\\section{')
        self.visitNodeDefault(node)
        self.writer('\\label{%s}}\n' % self.filename)

    mapStart_title = mapEnd_title = mapEnd_body = mapStart_body = \
    mapStart_html = None


def processFile(spitter, fin):
    dom = microdom.parse(fin).documentElement
    spitter.visitNode(dom)
