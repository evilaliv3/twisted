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

import latex

def texiEscape(text):
    return text.replace('\n', ' ')

entities = latex.copy()
entities['copy'] = '@copyright{}'

class TexiSpitter(latex.BaseLatexSpitter):

    baseLevel = 1

    def writeNodeData(self, node):
        buf = StringIO()
        latex.getLatexText(node, self.writer, texiEscape, entities)

    def visitNode_title(self, node):
        self.writer('@section ')
        self.visitNodeDefault(node)
        self.writer('\n')
        self.writer('@node ')
        self.visitNodeDefault(node)
        self.writer('\n')

    def visitNode_pre(self, node):
        self.writer('@verbatim\n')
        buf = StringIO()
        latex.getLatexText(node, buf.write, entities=entities)
        self.writer(text.removeLeadingTrailingBlanks(buf.getvalue()))
        self.writer('@end verbatim\n')

    def visitNode_code(self, node):
        fout = StringIO()
        latex.getLatexText(node, fout.write, texiEscape, entities)
        self.writer('@code{'+data+'}')

    def convert_png(self, src, target):
        os.system("pngtopnm %s | pnmtops > %s" % (src, target))

    def visitNodeHeader(self, node):
        level = (int(node.tagName[1])-2)+self.baseLevel
        self.writer('\n\n@'+level*'sub'+'section{')
        self.visitNodeDefault(node)
        self.writer('}\n')

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('@verbatim\n')
        self.writer(open(fileName).read())
        self.writer('@end verbatim')
        # Write a caption for this source listing

    def visitNode_a_href(self, node):
        self.visitNodeDefault(node)

    def visitNode_a_name(self, node):
        self.visitNodeDefault(node)

    visitNode_h2 = visitNode_h3 = visitNode_h4 = visitNodeHeader

    start_dl = '@itemize\n'
    end_dl = '@end itemize\n'
    start_ul = '@itemize\n'
    end_ul = '@end itemize\n'

    start_ol = '@enumerate\n'
    end_ol = '@end enumerate\n'

    start_li = '@item\n'
    end_li = '\n'

    start_dt = '@item'
    end_dt = ': '
    end_dd = '\n'

    start_p = '\n\n'

    start_strong = start_em = '@emph{'
    end_strong = end_em = '}'

    start_q = "``"
    end_q = "''"

    start_span_footnote = '@footnote{'
    end_span_footnote = '}'

    start_div_note = '@quotation\n@strong{Note:}'
    end_div_note = '@end quotation\n'

    start_th = '@strong{'
    end_th = '}'
