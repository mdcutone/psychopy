#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes and functions for transcribing speech in audio data to text.

Plugins which add additional transcribers use this module as an entry point. You
can acquire references to these classes by calling :func:`getTranscribers()`.

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'NULL_TRANSCRIPTION_RESULT',
    'TRANSCR_LANG_DEFAULT',
    'TranscriptionResult',
    'BaseTranscriber',
    'TranscriberPocketSphinx',
    'TranscriberGoogle',
    'getTranscribers',
    'transcribe',
    'recognizerEngineValues'
]

import os
import sys

import psychopy.logging as logging
from psychopy.alerts import alert
from pathlib import Path
from psychopy.preferences import prefs
from psychopy.sound.audioclip import *
from psychopy.sound.exceptions import *

# Constants related to the transcription system.
TRANSCR_LANG_DEFAULT = 'en-US'

# Values for specifying recognizer engines. This dictionary is used by Builder
# to populate the component property dropdown.
recognizerEngineValues = {
    0: ('sphinx', "CMU Pocket Sphinx", "Offline, Built-in"),
    1: ('google', "Google Cloud Speech API", "Online, Key Required"),
}


# ------------------------------------------------------------------------------
# Classes and functions for speech-to-text transcription
#

class TranscriptionResult:
    """Descriptor for returned transcription data.

    Fields within this class can be used to access transcribed words and other
    information related to the transcription request.

    This is returned by functions and methods which perform speech-to-text
    transcription from audio data within PsychoPy. The user usually does not
    create instances of this class themselves.

    Parameters
    ----------
    words : list of str
        Words extracted from the audio clip.
    unknownValue : bool
        `True` if the transcription API failed make sense of the audio and did
        not complete the transcription.
    requestFailed : bool
        `True` if there was an error with the transcriber itself. For instance,
        network error or improper formatting of the audio data.
    engine : str
        Name of engine used to perform this transcription.
    language : str
        Identifier for the language used to perform the transcription.

    """
    __slots__ = [
        '_words',
        '_confidence',  # unused on Python for now
        '_engine',
        '_language',
        '_expectedWords',
        '_requestFailed',
        '_unknownValue']

    def __init__(self, words, unknownValue, requestFailed, engine, language):
        self.words = words
        self.unknownValue = unknownValue
        self.requestFailed = requestFailed
        self.engine = engine
        self.language = language

    def __repr__(self):
        return (f"TranscriptionResult(words={self._words}, "
                f"unknownValue={self._unknownValue}, ",
                f"requestFailed={self._requestFailed}, ",
                f"engine={self._engine}, ",
                f"language={self._language})")

    def __str__(self):
        return " ".join(self._words)

    @property
    def wordCount(self):
        """Number of words found (`int`)."""
        return len(self._words)

    @property
    def words(self):
        """Words extracted from the audio clip (`list` of `str`)."""
        return self._words

    @words.setter
    def words(self, value):
        self._words = list(value)

    @property
    def success(self):
        """`True` if the transcriber returned a result successfully (`bool`)."""
        return not (self._unknownValue or self._requestFailed)

    @property
    def error(self):
        """`True` if there was an error during transcription (`bool`). Value is
        always the compliment of `.success`."""
        return not self.success

    @property
    def unknownValue(self):
        """`True` if the transcription API failed make sense of the audio and
        did not complete the transcription (`bool`).
        """
        return self._unknownValue

    @unknownValue.setter
    def unknownValue(self, value):
        self._unknownValue = bool(value)

    @property
    def requestFailed(self):
        """`True` if there was an error with the transcriber itself (`bool`).
        For instance, network error or improper formatting of the audio data,
        invalid key, or if there was network connection error.
        """
        return self._requestFailed

    @requestFailed.setter
    def requestFailed(self, value):
        self._requestFailed = bool(value)

    @property
    def engine(self):
        """Name of engine used to perform this transcription (`str`).
        """
        return self._engine

    @engine.setter
    def engine(self, value):
        self._engine = str(value)

    @property
    def language(self):
        """Identifier for the language used to perform the transcription
        (`str`).
        """
        return self._language

    @language.setter
    def language(self, value):
        self._language = str(value)


# empty result returned when a transcriber is given no data
NULL_TRANSCRIPTION_RESULT = TranscriptionResult(
    words=[''],
    unknownValue=False,
    requestFailed=False,
    engine='null',
    language=TRANSCR_LANG_DEFAULT
)


# ------------------------------------------------------------------------------
# Transcription Interface Classes
#

class BaseTranscriber:
    """Base class for all transcription interfaces.

    This class defines the minimal interface for transcribers. All plugins which
    implement new transcription interfaces should be conformant with the API
    specified by this class.

    All transcription interfaces are singletons as we usually cannot open
    multiple recognizers in parallel.

    """
    # Set these values appropriately in sub-classes, they are needed to identify
    # the transcriber whe unbound and give information to the user.
    transcriberType = 'unknown'
    transcriberDesc = 'Base transcriber class'

    # reference to the singleton instance stored here
    _instance = None
    _initialized = False  # set to `True` after `setupModel` is called

    # internal stuff to keep track of
    _language = None

    def __new__(cls, *args, **kwargs):
        """Control how this class is initialized to ensure only one instance is
        created per session to avoid overhead in creating recognizers.
        """
        if cls._instance is None:
            cls._instance = super(BaseTranscriber, cls).__new__(cls)

        return cls._instance

    def initialize(self, language=None):
        """Configure the recognizer model.

        This is called automatically on the first call to `transcribe`, but it
        can be called in advance to avoid doing so in a time-sensitive part of
        the program.

        """
        # bare minimum implementation, should set these as such
        self._language = language or self.language
        if self._language is None:
            self._language = TRANSCR_LANG_DEFAULT
            logging.warning(
                "Initializing model without specifying `language`. Using "
                "default value of '{}'.".format(TRANSCR_LANG_DEFAULT))

        # setup the transcriber here ...

        self._initialized = True  # idempotent after the first call

    @property
    def engine(self):
        """Transcription engine in use (`str`).

        This can refer to the transcription service itself, or just the
        recognizer in use.
        """
        return self.transcriberType

    @property
    def recognizer(self):
        """Alias of `BaseTranscriber.engine`.
        """
        return self.engine

    @property
    def language(self):
        """Language this transcriber was initialized to use (`str`).
        """
        return self._language

    @language.setter
    def language(self, val):
        self._language = val

    def transcribe(self, audioClip=None, language='en-US', expectedWords=None,
                   config=None):
        """Transcribe speech in the specified audio clip.

        Parameters
        ----------
        audioClip : AudioClip
            Audio clip containing speech samples to transcribe.
        language : str or None
            BCP-47 language code (eg., 'en-US'). Should match the language which
            the speaker is using. If `None`, the value at property `language` is
            used instead.
        expectedWords : list or None
            List of strings representing expected words or phrases. These are
            passed as speech context metadata which will make the recognizer
            prefer a particular word in cases where there is ambiguity or
            uncertainty.
        config : dict or None
            Additional configuration options for the recognizer as a dictionary.

        Returns
        -------
        TranscriptionResult
            Object containing the transcription result.

        """
        # transcribe should always do this check
        if not self._initialized:
            self.initialize(language=self.language)
            logging.warning(
                "Initializing the recognizer model. If you are experiencing "
                "timing issues, call `.initialize()` in some other part of "
                "the program.")

        return NULL_TRANSCRIPTION_RESULT  # dummy object


class TranscriberPocketSphinx(BaseTranscriber):
    """Speech-to-text transcription interface using CMU PocketSphinx.

    PocketSphinx is a locally hosted service that does speech-to-text
    transcription for free.

    """
    transcriberType = 'sphinx'
    transcriberDesc = "CMU Pocket Sphinx"

    _speechRecognition = None
    _sphinxModelPath = None
    _sphinxLangs = None
    _pocketSphinxRec = None

    def initialize(self, language=None):
        """Configure the recognizer model.

        This is called automatically on the first call to `transcribe`, but it
        can be called in advance to avoid doing so in a time-sensitive part of
        the program.

        """
        # bare minimum implementation, should set these as such
        self._language = language or self.language
        if self._language is None:
            self._language = TRANSCR_LANG_DEFAULT
            logging.warning(
                "Initializing model without specifying `language`. Using "
                "default value of '{}'.".format(TRANSCR_LANG_DEFAULT))

        try:
            import speech_recognition as sr
            import pocketsphinx
        except (ImportError, ModuleNotFoundError):
            logging.error(
                "Speech-to-text recognition module for PocketSphinx is not "
                "available (use command `pip install SpeechRecognition` to get "
                "it). Transcription will be unavailable using that service "
                "this session.")
            raise

        self._speechRecognition = sr  # keep link to library

        # check which language models we have available
        self._sphinxModelPath = pocketsphinx.get_model_path()
        self._sphinxLangs = [
            folder.stem for folder in Path(
                self._sphinxModelPath).glob('??-??')]

        # create the recognizer
        self._pocketSphinxRec = self._speechRecognition.Recognizer()

        self._initialized = True  # idempotent after the first call

    def transcribe(self, audioClip=None, language='en-US', expectedWords=None,
                   config=None):
        """Perform speech-to-text conversion on the provided audio samples using
        CMU Pocket Sphinx.

        Parameters
        ----------
        audioClip : :class:`~psychopy.sound.AudioClip` or None
            Audio clip containing speech to transcribe (e.g., recorded from a
            microphone). Specify `None` to open a client without performing a
            transcription, this will reduce latency when the transcriber is
            invoked in successive calls.
        language : str or None
            BCP-47 language code (eg., 'en-US'). Should match the language which
            the speaker is using. Pocket Sphinx requires language packs to be
            installed locally.
        expectedWords : list or None
            List of strings representing expected words or phrases. This will
            attempt bias the possible output words to the ones specified if the
            engine is uncertain. Sensitivity can be specified for each expected
            word. You can indicate the sensitivity level to use by putting a
            ``:`` after each word in the list (see the Example below).
            Sensitivity levels range between 0 and 100. A higher number results
            in the engine being more conservative, resulting in a higher
            likelihood of false rejections. The default sensitivity is 80% for
            words/phrases without one specified.
        config : dict or None
            Additional configuration options for the specified engine.

        Returns
        -------
        TranscriptionResult
            Transcription result object.

        """
        if not self._initialized:
            self.initialize(language=self.language)
            logging.warning(
                "Initializing the recognizer model. If you are experiencing "
                "timing issues, call `.initialize()` in some other part of "
                "the program.")

        # check if we have a valid audio clip
        if not isinstance(audioClip, AudioClip):
            raise TypeError(
                "Expected parameter `audioClip` to have type "
                "`psychopy.sound.AudioClip`.")

        # engine configuration
        config = {} if config is None else config
        if not isinstance(config, dict):
            raise TypeError(
                "Invalid type for parameter `config` specified, must be `dict` "
                "or `None`.")

        if language is None:  # use the property
            language = self.language
        elif not isinstance(language, str):
            raise TypeError(
                "Invalid type for parameter `language`, must be type `str` or "
                "`NoneType`.")

        language = language.lower()
        if language not in self._sphinxLangs:  # missing a language pack error
            url = "https://sourceforge.net/projects/cmusphinx/files/" \
                  "Acoustic%20and%20Language%20Models/"
            msg = (f"Language `{language}` is not installed for "
                   f"`pocketsphinx`. You can download languages here: {url}. "
                   f"Install them here: {self._sphinxModelPath}")
            raise RecognizerLanguageNotSupportedError(msg)

        # configure the recognizer
        config['language'] = language  # sphinx users en-us not en-US
        config['show_all'] = False
        if expectedWords is not None:
            words, sens = _parseExpectedWords(expectedWords)
            config['keyword_entries'] = tuple(zip(words, sens))

        # convert audio to format for transcription
        sampleWidth = 2  # two bytes per sample
        audioData = self._speechRecognition.AudioData(
            audioClip.asMono().convertToWAV(),
            sample_rate=audioClip.sampleRateHz,
            sample_width=sampleWidth)

        # submit audio samples to the API
        respAPI = ''
        unknownValueError = requestError = False
        try:
            respAPI = self._pocketSphinxRec.recognize_sphinx(
                audioData, **config)
        except self._speechRecognition.UnknownValueError:
            unknownValueError = True
        except self._speechRecognition.RequestError:
            requestError = True

        # remove empty words
        result = [word for word in respAPI.split(' ') if word != '']

        # object to return containing transcription data
        toReturn = TranscriptionResult(
            words=result,
            unknownValue=unknownValueError,
            requestFailed=requestError,
            engine=self.engine,
            language=language)

        # split only if the user does not want the raw API data
        return toReturn


class TranscriberGoogle(BaseTranscriber):
    """Speech-to-text transcription interface using Google Cloud services.

    This is an online based speech-to-text engine provided by Google as a
    subscription service, providing exceptional accuracy compared to `built-in`.
    Requires an API key to use which you must generate and specify prior to
    using this interface.

    """
    transcriberType = 'google'
    transcriberDesc = "Google Cloud"

    # internal class attributes the user doesn't need to see
    _googleCloudSpeech = None  # ref to speech module
    _googleCloudErrors = None  # ref to exceptions
    _googleCloudClient = None  # ref to client

    def initialize(self, language=None):
        """Configure the recognizer model.

        This is called automatically on the first call to `transcribe`, but it
        can be called in advance to avoid doing so in a time-sensitive part of
        the program.

        Parameters
        ----------
        language : str or None
            Language to initialize the recognizer with. This is specified as a
            BCP-47 language code (eg., 'en-US'). Should match the language which
            the speaker is using. This value is used when the `language`
            argument of `transcribe` is specified as `None`.

        """
        # set model language
        self._language = language or self.language
        if self._language is None:
            self._language = TRANSCR_LANG_DEFAULT
            logging.warning(
                "Initializing model without specifying `language`. Using "
                "default value of '{}'.".format(TRANSCR_LANG_DEFAULT))

        # do imports for google
        try:
            import google.cloud.speech as speech
            import google.auth.exceptions as errors
        except (ImportError, ModuleNotFoundError):
            logging.error(
                "Speech-to-text recognition using Google online services is "
                "not available (use command `pip install google-api-core "
                "google-auth google-cloud google-cloud-speech "
                "googleapis-common-protos` to get it). Transcription will be "
                "unavailable using that service this session.")
            raise

        self._googleCloudSpeech = speech
        self._googleCloudErrors = errors

        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
                prefs.general['appKeyGoogleCloud']

        # empty string indicates no key has been specified, raise error
        if not os.environ["GOOGLE_APPLICATION_CREDENTIALS"]:
            raise RecognizerAPICredentialsError(
                'No application key specified for Google Cloud Services, '
                'specify the path to the key file with either the system '
                'environment variable `GOOGLE_APPLICATION_CREDENTIALS` or in '
                'preferences (General -> appKeyGoogleCloud).')

        # open new client, takes a while the first go
        try:
            self._googleCloudClient = self._googleCloudSpeech.SpeechClient()
        except self._googleCloudErrors.DefaultCredentialsError:
            raise RecognizerAPICredentialsError(
                'Invalid key specified for Google Cloud Services, check if the '
                'key file is valid and readable.')

        self._initialized = True

    def transcribe(self, audioClip=None, language='en-US', expectedWords=None,
                   config=None):
        """Perform speech-to-text conversion on the provided audio clip using
        the Google Cloud API.

        Parameters
        ----------
        audioClip : :class:`~psychopy.sound.AudioClip` or None
            Audio clip containing speech to transcribe (e.g., recorded from a
            microphone). Specify `None` to open a client without performing a
            transcription, this will reduce latency when the transcriber is
            invoked in successive calls.
        language : str
            BCP-47 language code (eg., 'en-US'). Should match the language which
            the speaker is using.
        expectedWords : list or None
            List of strings representing expected words or phrases. These are
            passed as speech context metadata which will make the recognizer
            prefer a particular word in cases where there is ambiguity or
            uncertainty.
        config : dict or None
            Additional configuration options for the recognizer as a dictionary.

        Notes
        -----
        * The first invocation of this function will take considerably longer to
          run that successive calls as the client has not been started yet. Only
          one instance of a recognizer client can be created per-session.

        Examples
        --------
        Specifying the API key to use Google's Cloud service for
        speech-to-text::

            import os
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
                "C:\\path\\to\\my\\key.json"

            # you can now call the transcriber
            results = recognizeGoogle(
                myRecording, expectedWords=['left', 'right'])
            if results.success:
                print("You said: {}".format(results.words[0]))

        """
        if not self._initialized:
            self.initialize(language=language)
            logging.info(
                "Initializing the recognizer for the first time. If you are "
                "experiencing timing issues, call `.initialize()` in some "
                "other part of the program.")

        # check if we have a valid audio clip
        if not isinstance(audioClip, AudioClip):
            raise TypeError(
                "Expected parameter `audioClip` to have type "
                "`psychopy.sound.AudioClip`.")

        if language is None:  # use the property
            language = self.language
        elif not isinstance(language, str):
            raise TypeError(
                "Invalid type for parameter `language`, must be type `str` or "
                "`NoneType`.")

        # configure the recognizer
        enc = self._googleCloudSpeech.RecognitionConfig.AudioEncoding.LINEAR16
        params = {
            'encoding': enc,
            'sample_rate_hertz': audioClip.sampleRateHz,
            'language_code': language,
            'model': 'command_and_search',
            'audio_channel_count': audioClip.channels,
            'max_alternatives': 1}

        if isinstance(config, dict):
            params.update(config)

        # speech context (i.e. expected phrases)
        if expectedWords is not None:
            expectedWords, _ = _parseExpectedWords(expectedWords)
            params['speech_contexts'] = \
                [self._googleCloudSpeech.SpeechContext(phrases=expectedWords)]

        # Detects speech in the audio file
        response = self._googleCloudClient.recognize(
            config=self._googleCloudSpeech.RecognitionConfig(**params),
            audio=self._googleCloudSpeech.RecognitionAudio(
                content=audioClip.convertToWAV()))

        # package up response
        result = [
            result.alternatives[0].transcript for result in response.results]
        toReturn = TranscriptionResult(
            words=result,
            unknownValue=False,  # not handled yet
            requestFailed=False,  # not handled yet
            engine=self.engine,
            language=language)

        return toReturn


def getTranscribers():
    """Get available transcribers.

    This gets all installed transcribers including those loaded from plugins.

    Returns
    -------
    dict
        Mapping of transcriber IDs (`str`) and interfaces (subclasses of
        `BaseTranscriber`).

    """
    from psychopy.plugins import discoverModuleClasses

    # get all transcribers in this namespace by type
    foundTranscribers = discoverModuleClasses(
        sys.modules[__name__],
        BaseTranscriber)

    toReturn = {}  # mapping to return with transcribers
    for name, interface in foundTranscribers.items():
        if name == 'BaseTranscriber':  # ignore base class
            continue

        if not hasattr(interface, 'engine'):
            logging.error(
                "Transcriber class `{}` does not define attribute "
                "`transcriberType`, skipping.".format(name))
            continue

        transcriberType = interface.transcriberType
        toReturn[transcriberType] = interface

    return toReturn


def _parseExpectedWords(wordList, defaultSensitivity=80):
    """Parse expected words list.

    This function is used internally by other functions and classes within the
    `transcribe` module.

    Expected words or phrases are usually specified as a list of strings. CMU
    Pocket Sphinx allows for additional 'sensitivity' values for each phrase
    ranging from *0* to *100*. This function will generate to lists, first with
    just words and another with specified sensitivity values. This allows the
    user to specify sensitivity levels which can be ignored if the recognizer
    engine does not support it.

    Parameters
    ----------
    wordList : list of str
        List of words of phrases. Sensitivity levels for each can be specified
        by putting a value at the end of each string separated with a colon `:`.
        For example, ``'hello:80'`` for 80% sensitivity on 'hello'. Values are
        normalized between *0.0* and *1.0* when returned.
    defaultSensitivity : int or float
        Default sensitivity to use if a word does not have one specified between
        0 and 100%.

    Returns
    -------
    tuple
        Returns list of expected words and list of normalized sensitivities for
        each.

    Examples
    --------
    Specifying expected words to CMU Pocket Sphinx::

        words = [('hello:95', 'bye:50')]
        expectedWords = zip(_parseExpectedWords(words))

    """
    defaultSensitivity = defaultSensitivity / 100.  # normalized

    sensitivities = []
    if wordList is not None:
        # sensitivity specified as `word:80`
        wordListTemp = []
        for word in wordList:
            wordAndSense = word.split(':')
            if len(wordAndSense) == 2:  # specified as `word:80`
                word, sensitivity = wordAndSense
                sensitivity = int(sensitivity) / 100.
            else:
                word = wordAndSense[0]
                sensitivity = defaultSensitivity  # default is 80% confidence

            wordListTemp.append(word)
            sensitivities.append(sensitivity)

        wordList = wordListTemp

    return wordList, sensitivities


def transcribe(audioClip, engine='sphinx', language='en-US', expectedWords=None,
               config=None):
    """Convert speech in audio to text.

    This feature passes the audio clip samples to a specified text-to-speech
    engine which will attempt to transcribe any speech within. The efficacy of
    the transcription depends on the engine selected, audio quality, and
    language support. By default, Pocket Sphinx is used which provides decent
    transcription capabilities offline for English and a few other languages.
    For more robust transcription capabilities with a greater range of language
    support, online providers such as Google may be used.

    Speech-to-text conversion blocks the main application thread when used on
    Python. Don't transcribe audio during time-sensitive parts of your
    experiment! This issue is known to the developers and will be fixed in a
    later release.

    Parameters
    ----------
    audioClip : :class:`~psychopy.sound.AudioClip` or tuple
        Audio clip containing speech to transcribe (e.g., recorded from a
        microphone). Can be either an :class:`~psychopy.sound.AudioClip` object
        or tuple where the first value is as a Nx1 or Nx2 array of audio
        samples (`ndarray`) and the second the sample rate (`int`) in Hertz
        (e.g., ``(samples, 480000)``).
    engine : str
        Speech-to-text engine to use. Can be one of 'sphinx' for CMU Pocket
        Sphinx or 'google' for Google Cloud.
    language : str
        BCP-47 language code (eg., 'en-US'). Note that supported languages
        vary between transcription engines.
    expectedWords : list or tuple
        List of strings representing expected words or phrases. This will
        constrain the possible output words to the ones specified. Note not all
        engines support this feature (only Sphinx and Google Cloud do at this
        time). A warning will be logged if the engine selected does not support
        this feature. CMU PocketSphinx has an additional feature where the
        sensitivity can be specified for each expected word. You can indicate
        the sensitivity level to use by putting a ``:`` after each word in the
        list (see the Example below). Sensitivity levels range between 0 and
        100. A higher number results in the engine being more conservative,
        resulting in a higher likelihood of false rejections. The default
        sensitivity is 80% for words/phrases without one specified.
    config : dict or None
        Additional configuration options for the specified engine. These
        are specified using a dictionary (ex. `config={'pfilter': 1}` will
        enable the profanity filter when using the `'google'` engine).

    Returns
    -------
    :class:`~psychopy.sound.transcribe.TranscriptionResult`
        Transcription result.

    Notes
    -----
    * Online transcription services (eg., Google) provide robust and accurate
      speech recognition capabilities with broader language support than offline
      solutions. However, these services may require a paid subscription to use,
      reliable broadband internet connections, and may not respect the privacy
      of your participants as their responses are being sent to a third-party.
      Also consider that a track of audio data being sent over the network can
      be large, users on metered connections may incur additional costs to run
      your experiment.
    * If the audio clip has multiple channels, they will be combined prior to
      being passed to the transcription service if needed.

    Examples
    --------
    Use a voice command as a response to a task::

        # after doing  microphone recording
        resp = mic.getRecording()

        transcribeResults = transcribe(resp)
        if transcribeResults.success:  # successful transcription
            words = transcribeResults.words
            if 'hello' in words:
                print('You said hello.')

    Specifying expected words with sensitivity levels when using CMU Pocket
    Sphinx:

        # expected words 90% sensitivity on the first two, default for the rest
        expectedWords = ['right:90', 'left:90', 'up', 'down']

        transcribeResults = transcribe(
            resp.samples,
            resp.sampleRateHz,
            expectedWords=expectedWords)

        if transcribeResults.success:  # successful transcription
            # process results ...

    Specifying the API key to use Google's Cloud service for speech-to-text::

        # set the environment variable
        import os
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
            "C:\\path\\to\\my\\key.json"

        # you can now call the transcriber ...
        results = transcribe(
            myRecording,
            engine='google',
            expectedWords=['left', 'right'])

        if results.success:
            print("You said: {}".format(results.words[0]))

    """
    # check if the engine parameter is valid
    engine = engine.lower()  # make lower case

    # check if we have necessary keys
    if engine in ('google',):
        alert(4615, strFields={'engine': engine})

    # if we got a tuple, convert to audio clip object
    if isinstance(audioClip, (tuple, list,)):
        samples, sampleRateHz = audioClip
        audioClip = AudioClip(samples, sampleRateHz)

    # pass data over to the appropriate engine for transcription
    if engine == 'built-in':
        engine = 'sphinx'

    try:
        recognizer = getTranscribers()[engine]
    except KeyError:
        raise ValueError(
            'Cannot find transcription `engine` matching `{}`.'.format(engine))

    return recognizer.transcribe(
            audioClip,
            language=language,
            expectedWords=expectedWords,
            config=config)


if __name__ == "__main__":
    pass
