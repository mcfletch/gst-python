# -*- Mode: Python; py-indent-offset: 4 -*-
import sys
import string
import traceback
import keyword

class VarList:
    """Nicely format a C variable list"""
    def __init__(self):
	self.vars = {}
    def add(self, ctype, name):
	if self.vars.has_key(ctype):
	    self.vars[ctype] = self.vars[ctype] + (name,)
	else:
	    self.vars[ctype] = (name,)
    def __str__(self):
	ret = []
	for type in self.vars.keys():
	    ret.append('    ')
	    ret.append(type)
	    ret.append(' ')
	    ret.append(string.join(self.vars[type], ', '))
	    ret.append(';\n')
	if ret:
            ret.append('\n')
            return string.join(ret, '')
	return ''

class WrapperInfo:
    """A class that holds information about variable defs, code
    snippets, etcd for use in writing out the function/method
    wrapper."""
    def __init__(self):
        self.varlist = VarList()
        self.parsestr = ''
        self.parselist = ['', 'kwlist']
        self.codebefore = []
        self.codeafter = []
        self.arglist = []
        self.kwlist = []
    def get_parselist(self):
        return string.join(self.parselist, ', ')
    def get_codebefore(self):
        return string.join(self.codebefore, '')
    def get_codeafter(self):
        return string.join(self.codeafter, '')
    def get_arglist(self):
        return string.join(self.arglist, ', ')
    def get_varlist(self):
        return str(self.varlist)
    def get_kwlist(self):
        ret = '    static char *kwlist[] = { %s };\n' % \
              string.join(self.kwlist + [ 'NULL' ], ', ')
        if not self.get_varlist():
            ret = ret + '\n'
        return ret

    def add_parselist(self, codes, parseargs, keywords):
        self.parsestr = self.parsestr + codes
        for arg in parseargs:
            self.parselist.append(arg)
        for kw in keywords:
            if keyword.iskeyword(kw):
                kw = kw + '_'
            self.kwlist.append('"%s"' % kw)

class ArgType:
    def write_param(self, ptype, pname, pdflt, pnull, info):
	"""Add code to the WrapperInfo instance to handle
	parameter."""
	raise RuntimeError, "write_param not implemented for %s" % \
              self.__class__.__name__
    def write_return(self, ptype, ownsreturn, info):
	"""Adds a variable named ret of the return type to
	info.varlist, and add any required code to info.codeafter to
	convert the return value to a python object."""
	raise RuntimeError, "write_return not implemented for %s" % \
              self.__class__.__name__

class NoneArg(ArgType):
    def write_return(self, ptype, ownsreturn, info):
        info.codeafter.append('    Py_INCREF(Py_None);\n' +
                              '    return Py_None;')

class StringArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
            if pdflt != 'NULL': pdflt = '"' + pdflt + '"'
	    info.varlist.add('char', '*' + pname + ' = ' + pdflt)
	else:
	    info.varlist.add('char', '*' + pname)
	info.arglist.append(pname)
	if pnull:
            info.add_parselist('z', ['&' + pname], [pname])
	else:
            info.add_parselist('s', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        if ownsreturn:
	    # have to free result ...
	    info.varlist.add('gchar', '*ret')
            info.codeafter.append('    if (ret) {\n' +
                                  '        PyObject *py_ret = PyString_FromString(ret);\n' +
                                  '        g_free(ret);\n' +
                                  '        return py_ret;\n' +
                                  '    }\n' +
                                  '    Py_INCREF(Py_None);\n' +
                                  '    return Py_None;')
	else:
	    info.varlist.add('const gchar', '*ret')
            info.codeafter.append('    if (ret)\n' +
                                  '        return PyString_FromString(ret);\n'+
                                  '    Py_INCREF(Py_None);\n' +
                                  '    return Py_None;')

class UCharArg(ArgType):
    # allows strings with embedded NULLs.
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('guchar', '*' + pname + ' = "' + pdflt + '"')
	else:
	    info.varlist.add('guchar', '*' + pname)
        info.varlist.add('int', pname + '_len')
	info.arglist.append(pname)
	if pnull:
            info.add_parselist('z#', ['&' + pname, '&' + pname + '_len'],
                               [pname])
	else:
            info.add_parselist('s#', ['&' + pname, '&' + pname + '_len'],
                               [pname])

class CharArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('char', pname + " = '" + pdflt + "'")
	else:
	    info.varlist.add('char', pname)
	info.arglist.append(pname)
        info.add_parselist('c', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
	info.varlist.add('gchar', 'ret')
        info.codeafter.append('    return PyString_FromStringAndSize(&ret, 1);')
class GUniCharArg(ArgType):
    param_tmpl = ('    if (py_%(name)s[1] != 0) {\n'
                  '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a 1 character unicode string");\n'
                  '        return NULL;\n'
                  '    }\n'
                  '    %(name)s = (gunichar)py_%(name)s[0];\n')
    dflt_tmpl = ('    if (py_%(name)s != NULL) {\n'
                 '        if (py_%(name)s[1] != 0) {\n'
                 '            PyErr_SetString(PyExc_TypeError, "%(name)s should be a 1 character unicode string");\n'
                 '            return NULL;\n'
                 '        }\n'
                 '        %(name)s = (gunichar)py_%(name)s[0];\n'
                 '     }\n')
    ret_tmpl = ('#if !defined(Py_UNICODE_SIZE) || Py_UNICODE_SIZE == 2\n'
                '    if (ret > 0xffff) {\n'
                '        PyErr_SetString(PyExc_RuntimeError, "returned character can not be represented in 16-bit unicode");\n'
                '        return NULL;\n'
                '    }\n'
                '#endif\n'
                '    py_ret = (Py_UNICODE)ret;\n'
                '    return PyUnicode_FromUnicode(&py_ret, 1);\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('gunichar', pname + " = '" + pdflt + "'")
            info.codebefore.append(self.dflt_tmpl % {'name':pname})
	else:
	    info.varlist.add('gunichar', pname)
            info.codebefore.append(self.param_tmpl % {'name':pname})
        info.varlist.add('Py_UNICODE', '*py_' + pname + ' = NULL')
	info.arglist.append(pname)
        info.add_parselist('u', ['&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('gunichar', 'ret')
        info.varlist.add('Py_UNICODE', 'py_ret')
        info.codeafter.append(self.ret_tmpl)
        

class IntArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('int', pname + ' = ' + pdflt)
	else:
	    info.varlist.add('int', pname)
	info.arglist.append(pname)
        info.add_parselist('i', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('int', 'ret')
        info.codeafter.append('    return PyInt_FromLong(ret);')

class BoolArg(IntArg):
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('int', 'ret')
        info.varlist.add('PyObject', '*py_ret')
        info.codeafter.append('    py_ret = ret ? Py_True : Py_False;\n'
                              '    Py_INCREF(py_ret);\n'
                              '    return py_ret;')

class TimeTArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('time_t', pname + ' = ' + pdflt)
	else:
	    info.varlist.add('time_t', pname)
	info.arglist.append(pname)
        info.add_parselist('i', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('time_t', 'ret')
        info.codeafter.append('    return PyInt_FromLong(ret);')

class ULongArg(ArgType):
    dflt = '    if (py_%(name)s)\n' \
           '        %(name)s = PyLong_AsUnsignedLong(py_%(name)s);\n'
    before = '    %(name)s = PyLong_AsUnsignedLong(py_%(name)s);\n'
    def write_param(self, ptype, pname, pdflt, pnull, info):
        if pdflt:
            info.varlist.add('gulong', pname + ' = ' + pdflt)
            info.codebefore.append(self.dflt % {'name':pname})            
        else:
            info.varlist.add('gulong', pname)
            info.codebefore.append(self.before % {'name':pname})            
        info.varlist.add('PyObject', "*py_" + pname + ' = NULL')
        info.arglist.append(pname)
        info.add_parselist('O!', ['&PyLong_Type', '&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('gulong', 'ret')
        info.codeafter.append('    return PyLong_FromUnsignedLong(ret);')

class Int64Arg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('gint64', pname + ' = ' + pdflt)
	else:
	    info.varlist.add('gint64', pname)
	info.arglist.append(pname)
        info.add_parselist('L', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('gint64', 'ret')
        info.codeafter.append('    return PyLong_FromLongLong(ret);')

class UInt64Arg(ArgType):
    dflt = '    if (py_%(name)s)\n' \
           '        %(name)s = PyLong_AsUnsignedLongLong(py_%(name)s);\n'
    before = '    %(name)s = PyLong_AsUnsignedLongLong(py_%(name)s);\n'
    def write_param(self, ptype, pname, pdflt, pnull, info):
        if pdflt:
            info.varlist.add('guint64', pname + ' = ' + pdflt)
            info.codebefore.append(self.dflt % {'name':pname})            
        else:
            info.varlist.add('guint64', pname)
            info.codebefore.append(self.before % {'name':pname})            
        info.varlist.add('PyObject', "*py_" + pname + ' = NULL')
        info.arglist.append(pname)
        info.add_parselist('O!', ['&PyLong_Type', '&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('guint64', 'ret')
        info.codeafter.append('    return PyLong_FromUnsignedLongLong(ret);')
        

class DoubleArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add('double', pname + ' = ' + pdflt)
	else:
	    info.varlist.add('double', pname)
	info.arglist.append(pname)
        info.add_parselist('d', ['&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('double', 'ret')
        info.codeafter.append('    return PyFloat_FromDouble(ret);')

class FileArg(ArgType):
    nulldflt = ('    if (py_%(name)s == Py_None)\n'
                '        %(name)s = NULL;\n'
                '    else if (py_%(name)s && PyFile_Check(py_%(name)s)\n'
                '        %s = PyFile_AsFile(py_%(name)s);\n'
                '    else if (py_%(name)s) {\n'
                '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a file object or None");\n'
                '        return NULL;\n' 
                '    }')
    null = ('    if (py_%(name)s && PyFile_Check(py_%(name)s)\n'
            '        %(name)s = PyFile_AsFile(py_%(name)s);\n'
            '    else if (py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a file object or None");\n'
            '        return NULL;\n'
            '    }\n')
    dflt = ('    if (py_%(name)s)\n'
            '        %(name)s = PyFile_AsFile(py_%(name)s);\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
	    if pdflt:
		info.varlist.add('FILE', '*' + pname + ' = ' + pdflt)
		info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
		info.codebefore.append(self.nulldflt % {'name':pname})
	    else:
		info.varlist.add('FILE', '*' + pname + ' = NULL')
		info.varlist.add('PyObject', '*py_' + pname)
		info.codebefore.append(self.null & {'name':pname})
            info.arglist.appned(pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
	else:
	    if pdflt:
		info.varlist.add('FILE', '*' + pname + ' = ' + pdflt)
		info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
		info.codebefore.append(self.dflt % {'name':pname})
		info.arglist.append(pname)
	    else:
		info.varlist.add('PyObject', '*' + pname)
		info.arglist.append('PyFile_AsFile(' + pname + ')')
            info.add_parselist('O!', ['&PyFile_Type', '&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
	info.varlist.add('FILE', '*ret')
        info.codeafter.append('    if (ret)\n' +
                              '        return PyFile_FromFile(ret, "", "", fclose);\n' +
                              '    Py_INCREF(Py_None);\n' +
                              '    return Py_None;')

class EnumArg(ArgType):
    enum = ('    if (pyg_enum_get_value(%(typecode)s, py_%(name)s, (gint *)&%(name)s))\n'
            '        return NULL;\n')
    def __init__(self, enumname, typecode):
	self.enumname = enumname
	self.typecode = typecode
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add(self.enumname, pname + ' = ' + pdflt)
	else:
	    info.varlist.add(self.enumname, pname)
	info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
	info.codebefore.append(self.enum % { 'typecode': self.typecode,
                                             'name': pname})
	info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname]);
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('gint', 'ret')
        info.codeafter.append('    return PyInt_FromLong(ret);')

class FlagsArg(ArgType):
    flag = ('    if (%(default)spyg_flags_get_value(%(typecode)s, py_%(name)s, (gint *)&%(name)s))\n'
            '        return NULL;\n')
    def __init__(self, flagname, typecode):
	self.flagname = flagname
	self.typecode = typecode
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pdflt:
	    info.varlist.add(self.flagname, pname + ' = ' + pdflt)
            default = "py_%s && " % (pname,)
	else:
	    info.varlist.add(self.flagname, pname)
            default = ""
	info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
        info.codebefore.append(self.flag % {'default':default,
                                            'typecode':self.typecode,
                                            'name':pname})
	info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('guint', 'ret')
        info.codeafter.append('    return PyInt_FromLong(ret);')

class ObjectArg(ArgType):
    # should change these checks to more typesafe versions that check
    # a little further down in the class heirachy.
    nulldflt = ('    if ((PyObject *)py_%(name)s == Py_None)\n'
                '        %(name)s = NULL;\n'
                '    else if (py_%(name)s && pygobject_check(py_%(name)s, &Py%(type)s_Type))\n'
                '        %(name)s = %(cast)s(py_%(name)s->obj);\n'
                '    else if (py_%(name)s) {\n'
                '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(type)s or None");\n'
                '        return NULL;\n'
                '    }\n')
    null = ('    if (py_%(name)s && pygobject_check(py_%(name)s, &Py%(type)s_Type))\n'
            '        %(name)s = %(cast)s(py_%(name)s->obj);\n'
            '    else if ((PyObject *)py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(type)s or None");\n'
            '        return NULL;\n'
            '    }\n')
    dflt = '    if (py_%(name)s)\n' \
           '        %(name)s = %(cast)s(py_%(name)s->obj);\n'
    def __init__(self, objname, parent, typecode):
	self.objname = objname
	self.cast = string.replace(typecode, '_TYPE_', '_', 1)
        self.parent = parent
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
	    if pdflt:
		info.varlist.add(self.objname, '*' + pname + ' = ' + pdflt)
		info.varlist.add('PyGObject', '*py_' + pname + ' = NULL')
		info.codebefore.append(self.nulldflt % {'name':pname,
                                                        'cast':self.cast,
                                                        'type':self.objname}) 
	    else:
		info.varlist.add(self.objname, '*' + pname + ' = NULL')
		info.varlist.add('PyGObject', '*py_' + pname)
		info.codebefore.append(self.null % {'name':pname,
                                                    'cast':self.cast,
                                                    'type':self.objname}) 
            info.arglist.append(pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
	else:
	    if pdflt:
		info.varlist.add(self.objname, '*' + pname + ' = ' + pdflt)
		info.varlist.add('PyGObject', '*py_' + pname + ' = NULL')
		info.codebefore.append(self.dflt % {'name':pname,
                                                    'cast':self.cast}) 
		info.arglist.append(pname)
                info.add_parselist('O', ['&Py%s_Type' % self.objname,
                                         '&py_' + pname], [pname])
	    else:
		info.varlist.add('PyGObject', '*' + pname)
		info.arglist.append('%s(%s->obj)' % (self.cast, pname))
                info.add_parselist('O!', ['&Py%s_Type' % self.objname,
                                          '&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        if ptype[-1] == '*': ptype = ptype[:-1]
        info.varlist.add(ptype, '*ret')
        if ownsreturn:
            info.varlist.add('PyObject', '*py_ret')
            info.codeafter.append('    py_ret = pygobject_new((GObject *)ret);\n'
                                  '    g_object_unref(ret);\n'
                                  '    return py_ret;')
        else:
            info.codeafter.append('    /* pygobject_new handles NULL checking */\n' +
                                  '    return pygobject_new((GObject *)ret);')

class BoxedArg(ArgType):
    # haven't done support for default args.  Is it needed?
    check = ('    if (pyg_boxed_check(py_%(name)s, %(typecode)s))\n'
             '        %(name)s = pyg_boxed_get(py_%(name)s, %(typename)s);\n'
             '    else {\n'
             '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(typename)s");\n'
             '        return NULL;\n'
             '    }\n')
    null = ('    if (pyg_boxed_check(py_%(name)s, %(typecode)s))\n'
            '        %(name)s = pyg_boxed_get(py_%(name)s, %(typename)s);\n'
            '    else if (py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(typename)s or None");\n'
            '        return NULL;\n'
            '    }\n')
    def __init__(self, ptype, typecode):
	self.typename = ptype
	self.typecode = typecode
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
            info.varlist.add(self.typename, '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname + ' = Py_None')
	    info.codebefore.append(self.null % {'name':  pname,
                                                'typename': self.typename,
                                                'typecode': self.typecode})
	else:
            info.varlist.add(self.typename, '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname)
	    info.codebefore.append(self.check % {'name':  pname,
                                                 'typename': self.typename,
                                                 'typecode': self.typecode})
        if ptype[-1] == '*':
            typename = ptype[:-1]
            if typename[:6] == 'const-': typename = typename[6:]
            if typename != self.typename:
                info.arglist.append('(%s *)%s' % (ptype[:-1], pname))
            else:
                info.arglist.append(pname)
        else:
            info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname])
    ret_tmpl = '    /* pyg_boxed_new handles NULL checking */\n' \
               '    return pyg_boxed_new(%(typecode)s, %(ret)s, %(copy)s, TRUE);'
    def write_return(self, ptype, ownsreturn, info):
        if ptype[-1] == '*':
            info.varlist.add(self.typename, '*ret')
            ret = 'ret'
        else:
            info.varlist.add(self.typename, 'ret')
            ret = '&ret'
            ownsreturn = 0 # of course it can't own a ref to a local var ...
        info.codeafter.append(self.ret_tmpl %
                              { 'typecode': self.typecode,
                                'ret': ret,
                                'copy': ownsreturn and 'FALSE' or 'TRUE'})

class CustomBoxedArg(ArgType):
    # haven't done support for default args.  Is it needed?
    null = ('    if (%(check)s(py_%(name)s))\n'
            '        %(name)s = %(get)s(py_%(name)s);\n'
            '    else if (py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(type)s or None");\n'
            '        return NULL;\n'
            '    }\n')
    def __init__(self, ptype, pytype, getter, new):
	self.pytype = pytype
	self.getter = getter
        self.checker = 'Py' + ptype + '_Check'
	self.new = new
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
            info.varlist.add(ptype[:-1], '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname + ' = Py_None')
	    info.codebefore.append(self.null % {'name':  pname,
                                                'get':   self.getter,
                                                'check': self.checker,
                                                'type':  ptype[:-1]})
	    info.arglist.append(pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
	else:
	    info.varlist.add('PyObject', '*' + pname)
	    info.arglist.append(self.getter + '(' + pname + ')')
            info.add_parselist('O!', ['&' + self.pytype, '&' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add(ptype[:-1], '*ret')
        info.codeafter.append('    if (ret)\n' +
                              '        return ' + self.new + '(ret);\n' +
                              '    Py_INCREF(Py_None);\n' +
                              '    return Py_None;')

class PointerArg(ArgType):
    # haven't done support for default args.  Is it needed?
    check = ('    if (pyg_pointer_check(py_%(name)s, %(typecode)s))\n'
             '        %(name)s = pyg_pointer_get(py_%(name)s, %(typename)s);\n'
             '    else {\n'
             '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(typename)s");\n'
             '        return NULL;\n'
             '    }\n')
    null = ('    if (pyg_pointer_check(py_%(name)s, %(typecode)s))\n'
            '        %(name)s = pyg_pointer_get(py_%(name)s, %(typename)s);\n'
            '    else if (py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a %(typename)s or None");\n'
            '        return NULL;\n'
            '    }\n')
    def __init__(self, ptype, typecode):
	self.typename = ptype
	self.typecode = typecode
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
            info.varlist.add(self.typename, '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname + ' = Py_None')
	    info.codebefore.append(self.null % {'name':  pname,
                                                'typename': self.typename,
                                                'typecode': self.typecode})
	else:
            info.varlist.add(self.typename, '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname)
	    info.codebefore.append(self.check % {'name':  pname,
                                                 'typename': self.typename,
                                                 'typecode': self.typecode})
        info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        if ptype[-1] == '*':
            info.varlist.add(self.typename, '*ret')
            info.codeafter.append('    /* pyg_pointer_new handles NULL checking */\n' +
                                  '    return pyg_pointer_new(' + self.typecode + ', ret);')
        else:
            info.varlist.add(self.typename, 'ret')
            info.codeafter.append('    /* pyg_pointer_new handles NULL checking */\n' +
                                  '    return pyg_pointer_new(' + self.typecode + ', &ret);')

class AtomArg(IntArg):
    atom = ('    %(name)s = pygdk_atom_from_pyobject(py_%(name)s);\n'
            '    if (PyErr_Occurred())\n'
            '        return NULL;\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
        info.varlist.add('GdkAtom', pname)
	info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
	info.codebefore.append(self.atom % {'name': pname})
	info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('GdkAtom', 'ret')
        info.codeafter.append('    return PyGdkAtom_New(ret);')

class GTypeArg(ArgType):
    gtype = ('    if ((%(name)s = pyg_type_from_object(py_%(name)s)) == 0)\n'
             '        return NULL;\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
        info.varlist.add('GType', pname)
	info.varlist.add('PyObject', '*py_' + pname + ' = NULL')
	info.codebefore.append(self.gtype % {'name': pname})
	info.arglist.append(pname)
        info.add_parselist('O', ['&py_' + pname], [pname])
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('GType', 'ret')
        info.codeafter.append('    return pyg_type_wrapper_new(ret);')

# simple GError handler.
class GErrorArg(ArgType):
    handleerror = ('    if (pyg_error_check(&%(name)s))\n'
                   '        return NULL;\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
        info.varlist.add('GError', '*' + pname + ' = NULL')
        info.arglist.append('&' + pname)
        info.codeafter.append(self.handleerror % { 'name': pname })

class GtkTreePathArg(ArgType):
    # haven't done support for default args.  Is it needed?
    normal = ('    %(name)s = pygtk_tree_path_from_pyobject(py_%(name)s);\n'
              '    if (!%(name)s) {\n'
              '        PyErr_SetString(PyExc_TypeError, "could not convert %(name)s to a GtkTreePath");\n'
              '        return NULL;\n'
              '    }\n')
    null = ('    if (py_%(name)s != Py_None) {\n'
            '        %(name)s = pygtk_tree_path_from_pyobject(py_%(name)s);\n'
            '        if (!%(name)s) {\n'
            '            PyErr_SetString(PyExc_TypeError, "could not convert %(name)s to a GtkTreePath");\n'
            '            return NULL;\n'
            '        }\n'
            '    }\n')
    null = ('    if (PyTuple_Check(py_%(name)s))\n'
            '        %(name)s = pygtk_tree_path_from_pyobject(py_%(name)s);\n'
            '    else if (py_%(name)s != Py_None) {\n'
            '        PyErr_SetString(PyExc_TypeError, "%(name)s should be a GtkTreePath or None");\n'
            '        return NULL;\n'
            '    }\n')
    freepath = ('    if (%(name)s)\n'
                '        gtk_tree_path_free(%(name)s);\n')
    def __init__(self):
        pass
    def write_param(self, ptype, pname, pdflt, pnull, info):
	if pnull:
            info.varlist.add('GtkTreePath', '*' + pname + ' = NULL')
	    info.varlist.add('PyObject', '*py_' + pname + ' = Py_None')
	    info.codebefore.append(self.null % {'name':  pname})
	    info.arglist.append(pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
	else:
            info.varlist.add('GtkTreePath', '*' + pname)
	    info.varlist.add('PyObject', '*py_' + pname)
            info.codebefore.append(self.normal % {'name': pname})
	    info.arglist.append(pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
        info.codeafter.append(self.freepath % {'name': pname})
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add('GtkTreePath', '*ret')
        if ownsreturn:
            info.codeafter.append('    if (ret) {\n'
                                  '        PyObject *py_ret = pygtk_tree_path_to_pyobject(ret);\n'
                                  '        gtk_tree_path_free(ret);\n'
                                  '        return py_ret;\n'
                                  '    }\n'
                                  '    Py_INCREF(Py_None);\n'
                                  '    return Py_None;')
        else:
            info.codeafter.append('    if (ret) {\n'
                                  '        PyObject *py_ret = pygtk_tree_path_to_pyobject(ret);\n'
                                  '        return py_ret;\n'
                                  '    }\n'
                                  '    Py_INCREF(Py_None);\n'
                                  '    return Py_None;')
						       
class GdkRectanglePtrArg(ArgType):
    normal = ('    if (!pygdk_rectangle_from_pyobject(py_%(name)s, &%(name)s))\n'
              '        return NULL;\n')
    null =   ('    if (py_%(name)s == Py_None)\n'
              '        %(name)s = NULL;\n'
              '    else if (pygdk_rectangle_from_pyobject(py_%(name)s, &%(name)s_rect))\n'
              '        %(name)s = &%(name)s_rect;\n'
              '    else\n'
              '            return NULL;\n')
    def write_param(self, ptype, pname, pdflt, pnull, info):
        if pnull:
            info.varlist.add('GdkRectangle', pname + '_rect = { 0, 0, 0, 0 }')
            info.varlist.add('GdkRectangle', '*' + pname)
            info.varlist.add('PyObject', '*py_' + pname + ' = Py_None')
            info.add_parselist('O', ['&py_' + pname], [pname])
            info.arglist.append(pname)
            info.codebefore.append(self.null % {'name':  pname})
        else:
            info.varlist.add('GdkRectangle', pname + ' = { 0, 0, 0, 0 }')
            info.varlist.add('PyObject', '*py_' + pname)
            info.add_parselist('O', ['&py_' + pname], [pname])
            info.arglist.append('&' + pname)
            info.codebefore.append(self.normal % {'name':  pname})

class GdkRectangleArg(ArgType):
    def write_return(self, ptype, ownsreturn, info):
	info.varlist.add('GdkRectangle', 'ret')
	info.codeafter.append('    return pyg_boxed_new(GDK_TYPE_RECTANGLE, &ret, TRUE, TRUE);')

class PyObjectArg(ArgType):
    def write_param(self, ptype, pname, pdflt, pnull, info):
        info.varlist.add('PyObject', '*' + pname)
        info.add_parselist('O', ['&' + pname], [pname])
        info.arglist.append(pname)
    def write_return(self, ptype, ownsreturn, info):
        info.varlist.add("PyObject", "*ret")
        if ownsreturn:
            info.codeafter.append('    if (ret) {\n'
                                  '       return ret;\n'
                                  '    }\n'
                                  '    Py_INCREF(Py_None);\n'
                                  '    return Py_None;')
        else:
            info.codeafter.append('    if (!ret) ret = Py_None;\n'
                                  '    Py_INCREF(ret);\n'
                                  '    return ret;')

class ArgMatcher:
    def __init__(self):
	self.argtypes = {}

    def register(self, ptype, handler):
	self.argtypes[ptype] = handler
    def register_enum(self, ptype, typecode):
        if typecode is None:
            typecode = "G_TYPE_NONE"
        self.register(ptype, EnumArg(ptype, typecode))
    def register_flag(self, ptype, typecode):
        if typecode is None:
            typecode = "G_TYPE_NONE"
	self.register(ptype, FlagsArg(ptype, typecode))
    def register_object(self, ptype, parent, typecode):
        oa = ObjectArg(ptype, parent, typecode)
        self.register(ptype, oa)  # in case I forget the * in the .defs
	self.register(ptype+'*', oa)
        if ptype == 'GdkPixmap':
            # hack to handle GdkBitmap synonym.
            self.register('GdkBitmap', oa)
            self.register('GdkBitmap*', oa)
    def register_boxed(self, ptype, typecode):
        if self.argtypes.has_key(ptype): return
        arg = BoxedArg(ptype, typecode)
        self.register(ptype, arg)
	self.register(ptype+'*', arg)
        self.register('const-'+ptype+'*', arg)
    def register_custom_boxed(self, ptype, pytype, getter, new):
        arg = CustomBoxedArg(ptype, pytype, getter, new)
	self.register(ptype+'*', arg)
        self.register('const-'+ptype+'*', arg)
    def register_pointer(self, ptype, typecode):
        arg = PointerArg(ptype, typecode)
        self.register(ptype, arg)
	self.register(ptype+'*', arg)
        self.register('const-'+ptype+'*', arg)

    def get(self, ptype):
        try:
            return self.argtypes[ptype]
        except KeyError:
            if ptype[:8] == 'GdkEvent' and ptype[-1] == '*':
                return self.argtypes['GdkEvent*']
            raise
    def object_is_a(self, otype, parent):
        if otype == None: return 0
        if otype == parent: return 1
        if not self.argtypes.has_key(otype): return 0
        return self.object_is_a(self.get(otype).parent, parent)

matcher = ArgMatcher()

arg = NoneArg()
matcher.register(None, arg)
matcher.register('none', arg)

arg = StringArg()
matcher.register('char*', arg)
matcher.register('gchar*', arg)
matcher.register('const-char*', arg)
matcher.register('char-const*', arg)
matcher.register('const-gchar*', arg)
matcher.register('gchar-const*', arg)
matcher.register('string', arg)
matcher.register('static_string', arg)

arg = UCharArg()
matcher.register('unsigned-char*', arg)
matcher.register('const-guchar*', arg)
matcher.register('guchar*', arg)

arg = CharArg()
matcher.register('char', arg)
matcher.register('gchar', arg)
matcher.register('guchar', arg)

arg = GUniCharArg()
matcher.register('gunichar', arg)

arg = IntArg()
matcher.register('int', arg)
matcher.register('gint', arg)
matcher.register('guint', arg)
matcher.register('short', arg)
matcher.register('gshort', arg)
matcher.register('gushort', arg)
matcher.register('long', arg)
matcher.register('glong', arg)
matcher.register('gsize', arg)
matcher.register('gssize', arg)
matcher.register('guint8', arg)
matcher.register('gint8', arg)
matcher.register('guint16', arg)
matcher.register('gint16', arg)
matcher.register('gint32', arg)

arg = BoolArg()
matcher.register('gboolean', arg)

arg = TimeTArg()
matcher.register('time_t', arg)

# If the system maxint is smaller than unsigned int, we need to use
# Long objects with PyLong_AsUnsignedLong
if sys.maxint >= (1L << 32):
    matcher.register('guint32', arg)
else:
    arg = ULongArg()
    matcher.register('guint32', arg)

arg = ULongArg()
matcher.register('gulong', arg)

arg = Int64Arg()
matcher.register('gint64', arg)
matcher.register('long-long', arg)

arg = UInt64Arg()
matcher.register('guint64', arg)
matcher.register('unsigned-long-long', arg)

arg = DoubleArg()
matcher.register('double', arg)
matcher.register('gdouble', arg)
matcher.register('float', arg)
matcher.register('gfloat', arg)

arg = FileArg()
matcher.register('FILE*', arg)

# enums, flags, objects

matcher.register('GdkAtom', AtomArg())

matcher.register('GType', GTypeArg())
matcher.register('GtkType', GTypeArg())

matcher.register('GError**', GErrorArg())
matcher.register('GtkTreePath*', GtkTreePathArg())
matcher.register('GdkRectangle*', GdkRectanglePtrArg())
matcher.register('GtkAllocation*', GdkRectanglePtrArg())
matcher.register('GdkRectangle', GdkRectangleArg())
matcher.register('PyObject*', PyObjectArg())

matcher.register('GdkNativeWindow', ULongArg())

matcher.register_object('GObject', None, 'G_TYPE_OBJECT')

del arg