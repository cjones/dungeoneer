
import sys
import os

__all__ = ['Platform', 'get_platform']

class Platform:
    WINDOWS = 'win32'
    OSX = 'darwin'
    LINUX = 'linux'
    OTHER = sys.platform


def get_platform():
    if (os.name == 'nt' or sys.platform == 'win32' or
            'ce' in sys.builtin_module_names):
        return Platform.WINDOWS
    if os.name != "posix" or not hasattr(os, 'uname'):
        # it's a mystery! someone's toaster or something
        return Platform.OTHER
    name = os.uname()[0].lower().replace('/', '')
    if name.startswith('linux'):
        return Platform.LINUX
    if name.startswith('darwin'):
        return Platform.OSX
    # possible platforms at this point include cygwin, sunos, aix, irix, etc..
    # honestly doesn't matter, it's unlikely to work. :P
    return Platform.OTHER

try:
    import termios, tty, select
    def get_input(timeout=None, bufsize=4096):
        ctty = os.ctermid()
        fd = os.open(ctty, os.O_RDWR)
        if os.isatty(fd):
            stty = termios.tcgetattr(fd)
            try:
                os.write(fd, '\x1b[?25l')  # civis (hide cursor)
                tty.setraw(fd)
                while True:
                    try:
                        r, w, e = select.select([fd], [], [fd], timeout)
                        if e:
                            break  # bad things happened
                        if not r and not w:
                            break  # timeout
                        if fd in r:
                            # in raw mode, this will collect sequences such as
                            # what arrow keys might return rather than single
                            # chars which may require more input to make sense
                            read = os.read(fd, bufsize)
                            if read and read.startswith('\x03'):
                                # user hit ^C
                                raise KeyboardInterrupt
                            return read
                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except (OSError, IOError, select.error), exc:
                        code = exc.args[0]
                        if code == errno.EIO:
                            break
                        if code not in {errno.EINTR, errno.EAGAIN}:
                            raise
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, stty)
                os.write(fd, '\x1b[?25h')  # cnorm (restore cursor)

except ImportError:
    get_input = raw_input
