import test.test_support, unittest
import sys, codecs, htmlentitydefs, unicodedata

class CodecCallbackTest(unittest.TestCase):

    def test_xmlcharrefreplace(self):
        # replace unencodable characters which numeric character entities.
        # For ascii, latin-1 and charmaps this is completely implemented
        # in C and should be reasonably fast.
        s = u"\u30b9\u30d1\u30e2 \xe4nd eggs"
        self.assertEqual(
            s.encode("ascii", "xmlcharrefreplace"),
            "&#12473;&#12497;&#12514; &#228;nd eggs"
        )
        self.assertEqual(
            s.encode("latin-1", "xmlcharrefreplace"),
            "&#12473;&#12497;&#12514; \xe4nd eggs"
        )

    def test_xmlcharnamereplace(self):
        # This time use a named character entity for unencodable
        # characters, if one is available.
        names = {}
        for (key, value) in htmlentitydefs.entitydefs.items():
            if len(value)==1:
                names[unicode(value, "latin-1")] = unicode(key, "latin-1")
            else:
                names[unichr(int(value[2:-1]))] = unicode(key, "latin-1")

        def xmlcharnamereplace(exc):
            if not isinstance(exc, UnicodeEncodeError):
                raise TypeError("don't know how to handle %r" % exc)
            l = []
            for c in exc.object[exc.start:exc.end]:
                try:
                    l.append(u"&%s;" % names[c])
                except KeyError:
                    l.append(u"&#%d;" % ord(c))
            return (u"".join(l), exc.end)

        codecs.register_error(
            "test.xmlcharnamereplace", xmlcharnamereplace)

        sin = u"\xab\u211c\xbb = \u2329\u1234\u20ac\u232a"
        sout = "&laquo;&real;&raquo; = &lang;&#4660;&euro;&rang;"
        self.assertEqual(sin.encode("ascii", "test.xmlcharnamereplace"), sout)
        sout = "\xab&real;\xbb = &lang;&#4660;&euro;&rang;"
        self.assertEqual(sin.encode("latin-1", "test.xmlcharnamereplace"), sout)
        sout = "\xab&real;\xbb = &lang;&#4660;\xa4&rang;"
        self.assertEqual(sin.encode("iso-8859-15", "test.xmlcharnamereplace"), sout)

    def test_uninamereplace(self):
        # We're using the names from the unicode database this time,
        # and we're doing "systax highlighting" here, i.e. we include
        # the replaced text in ANSI escape sequences. For this it is
        # useful that the error handler is not called for every single
        # unencodable character, but for a complete sequence of
        # unencodable characters, otherwise we would output many
        # unneccessary escape sequences.

        def uninamereplace(exc):
            if not isinstance(exc, UnicodeEncodeError):
                raise TypeError("don't know how to handle %r" % exc)
            l = []
            for c in exc.object[exc.start:exc.end]:
                l.append(unicodedata.name(c, u"0x%x" % ord(c)))
            return (u"\033[1m%s\033[0m" % u", ".join(l), exc.end)

        codecs.register_error(
            "test.uninamereplace", uninamereplace)

        sin = u"\xac\u1234\u20ac\u8000"
        sout = "\033[1mNOT SIGN, ETHIOPIC SYLLABLE SEE, EURO SIGN, CJK UNIFIED IDEOGRAPH-8000\033[0m"
        self.assertEqual(sin.encode("ascii", "test.uninamereplace"), sout)

        sout = "\xac\033[1mETHIOPIC SYLLABLE SEE, EURO SIGN, CJK UNIFIED IDEOGRAPH-8000\033[0m"
        self.assertEqual(sin.encode("latin-1", "test.uninamereplace"), sout)

        sout = "\xac\033[1mETHIOPIC SYLLABLE SEE\033[0m\xa4\033[1mCJK UNIFIED IDEOGRAPH-8000\033[0m"
        self.assertEqual(sin.encode("iso-8859-15", "test.uninamereplace"), sout)

    def test_backslashescape(self):
        # Does the same as the "unicode-escape" encoding, but with different
        # base encodings.
        sin = u"a\xac\u1234\u20ac\u8000"
        if sys.maxunicode > 0xffff:
            sin += unichr(sys.maxunicode)
        sout = "a\\xac\\u1234\\u20ac\\u8000"
        if sys.maxunicode > 0xffff:
            sout += "\\U%08x" % sys.maxunicode
        self.assertEqual(sin.encode("ascii", "backslashreplace"), sout)

        sout = "a\xac\\u1234\\u20ac\\u8000"
        if sys.maxunicode > 0xffff:
            sout += "\\U%08x" % sys.maxunicode
        self.assertEqual(sin.encode("latin-1", "backslashreplace"), sout)

        sout = "a\xac\\u1234\xa4\\u8000"
        if sys.maxunicode > 0xffff:
            sout += "\\U%08x" % sys.maxunicode
        self.assertEqual(sin.encode("iso-8859-15", "backslashreplace"), sout)

    def test_relaxedutf8(self):
        # This is the test for a decoding callback handler,
        # that relaxes the UTF-8 minimal encoding restriction.
        # A null byte that is encoded as "\xc0\x80" will be
        # decoded as a null byte. All other illegal sequences
        # will be handled strictly.
        def relaxedutf8(exc):
            if not isinstance(exc, UnicodeDecodeError):
                raise TypeError("don't know how to handle %r" % exc)
            if exc.object[exc.start:exc.end].startswith("\xc0\x80"):
                return (u"\x00", exc.start+2) # retry after two bytes
            else:
                raise exc

        codecs.register_error(
            "test.relaxedutf8", relaxedutf8)

        sin = "a\x00b\xc0\x80c\xc3\xbc\xc0\x80\xc0\x80"
        sout = u"a\x00b\x00c\xfc\x00\x00"
        self.assertEqual(sin.decode("utf-8", "test.relaxedutf8"), sout)
        sin = "\xc0\x80\xc0\x81"
        self.assertRaises(UnicodeError, sin.decode, "utf-8", "test.relaxedutf8")

    def test_charmapencode(self):
        # For charmap encodings the replacement string will be
        # mapped through the encoding again. This means, that
        # to be able to use e.g. the "replace" handler, the
        # charmap has to have a mapping for "?".
        charmap = dict([ (ord(c), 2*c.upper()) for c in "abcdefgh"])
        sin = u"abc"
        sout = "AABBCC"
        self.assertEquals(codecs.charmap_encode(sin, "strict", charmap)[0], sout)

        sin = u"abcA"
        self.assertRaises(UnicodeError, codecs.charmap_encode, sin, "strict", charmap)

        charmap[ord("?")] = "XYZ"
        sin = u"abcDEF"
        sout = "AABBCCXYZXYZXYZ"
        self.assertEquals(codecs.charmap_encode(sin, "replace", charmap)[0], sout)

        charmap[ord("?")] = u"XYZ"
        self.assertRaises(TypeError, codecs.charmap_encode, sin, "replace", charmap)

        charmap[ord("?")] = u"XYZ"
        self.assertRaises(TypeError, codecs.charmap_encode, sin, "replace", charmap)

    def test_callbacks(self):
        def handler1(exc):
            if not isinstance(exc, UnicodeEncodeError) \
               and not isinstance(exc, UnicodeDecodeError):
                raise TypeError("don't know how to handle %r" % exc)
            l = [u"<%d>" % ord(exc.object[pos]) for pos in xrange(exc.start, exc.end)]
            return (u"[%s]" % u"".join(l), exc.end)

        codecs.register_error("test.handler1", handler1)

        def handler2(exc):
            if not isinstance(exc, UnicodeDecodeError):
                raise TypeError("don't know how to handle %r" % exc)
            l = [u"<%d>" % ord(exc.object[pos]) for pos in xrange(exc.start, exc.end)]
            return (u"[%s]" % u"".join(l), exc.end+1) # skip one character

        codecs.register_error("test.handler2", handler2)

        s = "\x00\x81\x7f\x80\xff"

        self.assertEqual(
            s.decode("ascii", "test.handler1"),
            u"\x00[<129>]\x7f[<128>][<255>]"
        )
        self.assertEqual(
            s.decode("ascii", "test.handler2"),
            u"\x00[<129>][<128>]"
        )

        self.assertEqual(
            "\\u3042\u3xxx".decode("unicode-escape", "test.handler1"),
            u"\u3042[<92><117><51><120>]xx"
        )

        self.assertEqual(
            "\\u3042\u3xx".decode("unicode-escape", "test.handler1"),
            u"\u3042[<92><117><51><120><120>]"
        )

        self.assertEqual(
            codecs.charmap_decode("abc", "test.handler1", {ord("a"): u"z"})[0],
            u"z[<98>][<99>]"
        )

        self.assertEqual(
            u"g\xfc\xdfrk".encode("ascii", "test.handler1"),
            u"g[<252><223>]rk"
        )

        self.assertEqual(
            u"g\xfc\xdf".encode("ascii", "test.handler1"),
            u"g[<252><223>]"
        )

    def test_longstrings(self):
        # test long strings to check for memory overflow problems
        errors = [ "strict", "ignore", "replace", "xmlcharrefreplace", "backslashreplace"]
        # register the handlers under different names,
        # to prevent the codec from recognizing the name
        for err in errors:
            codecs.register_error("test." + err, codecs.lookup_error(err))
        l = 1000
        errors += [ "test." + err for err in errors ]
        for uni in [ s*l for s in (u"x", u"\u3042", u"a\xe4") ]:
            for enc in ("ascii", "latin-1", "iso-8859-1", "iso-8859-15", "utf-8", "utf-7", "utf-16"):
                for err in errors:
                    try:
                        uni.encode(enc, err)
                    except UnicodeError:
                        pass

    def check_exceptionobjectargs(self, exctype, args, msg):
        # Test UnicodeError subclasses: construction, attribute assignment and __str__ conversion
        # check with one missing argument
        self.assertRaises(TypeError, exctype, *args[:-1])
        # check with one missing argument
        self.assertRaises(TypeError, exctype, *(args + ["too much"]))
        # check with one argument of the wrong type
        wrongargs = [ "spam", u"eggs", 42, 1.0, None ]
        for i in xrange(len(args)):
            for wrongarg in wrongargs:
                if type(wrongarg) is type(args[i]):
                    continue
                # build argument array
                callargs = []
                for j in xrange(len(args)):
                    if i==j:
                        callargs.append(wrongarg)
                    else:
                        callargs.append(args[i])
                self.assertRaises(TypeError, exctype, *callargs)
        exc = exctype(*args)
        self.assertEquals(str(exc), msg)

    def test_unicodeencodeerror(self):
        self.check_exceptionobjectargs(
            UnicodeEncodeError,
            ["ascii", u"g\xfcrk", 1, 2, "ouch"],
            "'ascii' codec can't encode character '\ufc' in position 1: ouch"
        )
        self.check_exceptionobjectargs(
            UnicodeEncodeError,
            ["ascii", u"g\xfcrk", 1, 4, "ouch"],
            "'ascii' codec can't encode characters in position 1-3: ouch"
        )
        self.check_exceptionobjectargs(
            UnicodeEncodeError,
            ["ascii", u"\xfcx", 0, 1, "ouch"],
            "'ascii' codec can't encode character '\ufc' in position 0: ouch"
        )

    def test_unicodedecodeerror(self):
        self.check_exceptionobjectargs(
            UnicodeDecodeError,
            ["ascii", "g\xfcrk", 1, 2, "ouch"],
            "'ascii' codec can't decode byte 0xfc in position 1: ouch"
        )
        self.check_exceptionobjectargs(
            UnicodeDecodeError,
            ["ascii", "g\xfcrk", 1, 3, "ouch"],
            "'ascii' codec can't decode bytes in position 1-2: ouch"
        )

    def test_unicodetranslateerror(self):
        self.check_exceptionobjectargs(
            UnicodeTranslateError,
            [u"g\xfcrk", 1, 2, "ouch"],
            "can't translate character '\\ufc' in position 1: ouch"
        )
        self.check_exceptionobjectargs(
            UnicodeTranslateError,
            [u"g\xfcrk", 1, 3, "ouch"],
            "can't translate characters in position 1-2: ouch"
        )

    def test_badandgoodstrictexceptions(self):
        self.assertRaises(
            TypeError,
            codecs.strict_errors,
            42
        )
        self.assertRaises(
            Exception,
            codecs.strict_errors,
            Exception("ouch")
        )

        self.assertRaises(
            UnicodeEncodeError,
            codecs.strict_errors,
            UnicodeEncodeError("ascii", u"\u3042", 0, 1, "ouch")
        )

    def test_badandgoodignoreexceptions(self):
        self.assertRaises(
           TypeError,
           codecs.ignore_errors,
           42
        )
        self.assertRaises(
           TypeError,
           codecs.ignore_errors,
           UnicodeError("ouch")
        )
        self.assertEquals(
            codecs.ignore_errors(UnicodeEncodeError("ascii", u"\u3042", 0, 1, "ouch")),
            (u"", 1)
        )
        self.assertEquals(
            codecs.ignore_errors(UnicodeDecodeError("ascii", "\xff", 0, 1, "ouch")),
            (u"", 1)
        )
        self.assertEquals(
            codecs.ignore_errors(UnicodeTranslateError(u"\u3042", 0, 1, "ouch")),
            (u"", 1)
        )

    def test_badandgoodreplaceexceptions(self):
        self.assertRaises(
           TypeError,
           codecs.replace_errors,
           42
        )
        self.assertRaises(
           TypeError,
           codecs.replace_errors,
           UnicodeError("ouch")
        )
        self.assertEquals(
            codecs.replace_errors(UnicodeEncodeError("ascii", u"\u3042", 0, 1, "ouch")),
            (u"?", 1)
        )
        self.assertEquals(
            codecs.replace_errors(UnicodeDecodeError("ascii", "\xff", 0, 1, "ouch")),
            (u"\ufffd", 1)
        )
        self.assertEquals(
            codecs.replace_errors(UnicodeTranslateError(u"\u3042", 0, 1, "ouch")),
            (u"\ufffd", 1)
        )

    def test_badandgoodxmlcharrefreplaceexceptions(self):
        self.assertRaises(
           TypeError,
           codecs.xmlcharrefreplace_errors,
           42
        )
        self.assertRaises(
           TypeError,
           codecs.xmlcharrefreplace_errors,
           UnicodeError("ouch")
        )
        self.assertEquals(
            codecs.xmlcharrefreplace_errors(UnicodeEncodeError("ascii", u"\u3042", 0, 1, "ouch")),
            (u"&#%d;" % 0x3042, 1)
        )
        self.assertRaises(
            TypeError,
            codecs.xmlcharrefreplace_errors,
            UnicodeError("ouch")
        )
        self.assertRaises(
            TypeError,
            codecs.xmlcharrefreplace_errors,
            UnicodeDecodeError("ascii", "\xff", 0, 1, "ouch")
        )
        self.assertRaises(
            TypeError,
            codecs.xmlcharrefreplace_errors,
            UnicodeTranslateError(u"\u3042", 0, 1, "ouch")
        )

    def test_badandgoodbackslashreplaceexceptions(self):
        self.assertRaises(
           TypeError,
           codecs.backslashreplace_errors,
           42
        )
        self.assertRaises(
           TypeError,
           codecs.backslashreplace_errors,
           UnicodeError("ouch")
        )
        self.assertEquals(
            codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\u3042", 0, 1, "ouch")),
            (u"\\u3042", 1)
        )
        self.assertEquals(
            codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\x00", 0, 1, "ouch")),
            (u"\\x00", 1)
        )
        self.assertEquals(
            codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\xff", 0, 1, "ouch")),
            (u"\\xff", 1)
        )
        self.assertEquals(
            codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\u0100", 0, 1, "ouch")),
            (u"\\u0100", 1)
        )
        self.assertEquals(
            codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\uffff", 0, 1, "ouch")),
            (u"\\uffff", 1)
        )
        if sys.maxunicode>0xffff:
            self.assertEquals(
                codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\U00010000", 0, 1, "ouch")),
                (u"\\U00010000", 1)
            )
            self.assertEquals(
                codecs.backslashreplace_errors(UnicodeEncodeError("ascii", u"\U0010ffff", 0, 1, "ouch")),
                (u"\\U0010ffff", 1)
            )

        self.assertRaises(
            TypeError,
            codecs.backslashreplace_errors,
            UnicodeError("ouch")
        )
        self.assertRaises(
            TypeError,
            codecs.backslashreplace_errors,
            UnicodeDecodeError("ascii", "\xff", 0, 1, "ouch")
        )
        self.assertRaises(
            TypeError,
            codecs.backslashreplace_errors,
            UnicodeTranslateError(u"\u3042", 0, 1, "ouch")
        )

    def test_badhandlerresults(self):
        results = ( 42, u"foo", (1,2,3), (u"foo", 1, 3), (u"foo", None), (u"foo",), ("foo", 1, 3), ("foo", None), ("foo",) )
        encs = ("ascii", "latin-1", "iso-8859-1", "iso-8859-15")

        for res in results:
            codecs.register_error("test.badhandler", lambda: res)
            for enc in encs:
                self.assertRaises(
                    TypeError,
                    u"\u3042".encode,
                    enc,
                    "test.badhandler"
                )
            for (enc, bytes) in (
                ("ascii", "\xff"),
                ("utf-8", "\xff"),
                ("utf-7", "+x-")
            ):
                self.assertRaises(
                    TypeError,
                    bytes.decode,
                    enc,
                    "test.badhandler"
                )

    def test_lookup(self):
        self.assertEquals(codecs.strict_errors, codecs.lookup_error("strict"))
        self.assertEquals(codecs.ignore_errors, codecs.lookup_error("ignore"))
        self.assertEquals(codecs.strict_errors, codecs.lookup_error("strict"))
        self.assertEquals(
            codecs.xmlcharrefreplace_errors,
            codecs.lookup_error("xmlcharrefreplace")
        )
        self.assertEquals(
            codecs.backslashreplace_errors,
            codecs.lookup_error("backslashreplace")
        )

    def test_unencodablereplacement(self):
        def unencrepl(exc):
            if isinstance(exc, UnicodeEncodeError):
                return (u"\u4242", exc.end)
            else:
                raise TypeError("don't know how to handle %r" % exc)
        codecs.register_error("test.unencreplhandler", unencrepl)
        for enc in ("ascii", "iso-8859-1", "iso-8859-15"):
            self.assertRaises(
                UnicodeEncodeError,
                u"\u4242".encode,
                enc,
                "test.unencreplhandler"
            )

def test_main():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CodecCallbackTest))
    test.test_support.run_suite(suite)

if __name__ == "__main__":
    test_main()
