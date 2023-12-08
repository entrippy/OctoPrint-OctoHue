import math
import logging
import networkx
from abc import ABCMeta, abstractmethod
from octoprint_octohue import colour_constants

logger = logging.getLogger(__name__)

class ConversionManager(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        self.registered_color_spaces = set()

    def add_type_conversion(self, start_type, target_type, conversion_function):
        """
        Register a conversion function between two color spaces.
        :param start_type: Starting color space.
        :param target_type: Target color space.
        :param conversion_function: Conversion function.
        """
        self.registered_color_spaces.add(start_type)
        self.registered_color_spaces.add(target_type)
        logger.debug("Registered conversion from %s to %s", start_type, target_type)

    @abstractmethod
    def get_conversion_path(self, start_type, target_type):
        """
        Return a list of conversion functions that if applied iteratively on a
        color of the start_type color space result in a color in the result_type
        color space.

        Raises an UndefinedConversionError if no valid conversion path
        can be found.

        :param start_type: Starting color space type.
        :param target_type: Target color space type.
        :return: List of conversion functions.
        """
        pass

    @staticmethod
    def _normalise_type(color_type):
        """
        Return the highest superclass that is valid for color space
        conversions (e.g., AdobeRGB -> BaseRGBColor).
        """
        if issubclass(color_type, BaseRGBColor):
            return BaseRGBColor
        else:
            return color_type

class ColorMathException(Exception):
    """
    Base exception for all colormath exceptions.
    """

    pass

class InvalidIlluminantError(ColorMathException):
    """
    Raised when an invalid illuminant is set on a ColorObj.
    """

    def __init__(self, illuminant):
        super(InvalidIlluminantError, self).__init__(illuminant)
        self.message = "Invalid illuminant specified: %s" % illuminant

class InvalidObserverError(ColorMathException):
    """
    Raised when an invalid observer is set on a ColorObj.
    """

    def __init__(self, cobj):
        super(InvalidObserverError, self).__init__(cobj)
        self.message = "Invalid observer angle specified: %s" % cobj.observer

class UndefinedConversionError(ColorMathException):
    """
    Raised when the user asks for a color space conversion that does not exist.
    """

    def __init__(self, cobj, cs_to):
        super(UndefinedConversionError, self).__init__(cobj, cs_to)
        self.message = "Conversion from %s to %s is not defined." % (cobj, cs_to)

class GraphConversionManager(ConversionManager):
    def __init__(self):
        super(GraphConversionManager, self).__init__()
        self.conversion_graph = networkx.DiGraph()

    def get_conversion_path(self, start_type, target_type):
        start_type = self._normalise_type(start_type)
        target_type = self._normalise_type(target_type)
        try:
            # Retrieve node sequence that leads from start_type to target_type.
            return self._find_shortest_path(start_type, target_type)
        except (networkx.NetworkXNoPath, networkx.NodeNotFound):
            raise UndefinedConversionError(
                start_type, target_type,
            )

    def _find_shortest_path(self, start_type, target_type):
        path = networkx.shortest_path(self.conversion_graph, start_type, target_type)
        # Look up edges between nodes and retrieve the conversion function
        # for each edge.
        return [
            self.conversion_graph.get_edge_data(node_a, node_b)["conversion_function"]
            for node_a, node_b in zip(path[:-1], path[1:])
        ]

    def add_type_conversion(self, start_type, target_type, conversion_function):
        super(GraphConversionManager, self).add_type_conversion(
            start_type, target_type, conversion_function
        )
        self.conversion_graph.add_edge(
            start_type, target_type, conversion_function=conversion_function
        )

class ColorBase(object):
    """
    A base class holding some common methods and values.
    """

    # Attribute names containing color data on the sub-class. For example,
    # sRGBColor would be ['rgb_r', 'rgb_g', 'rgb_b']
    VALUES = []
    # If this object as converted such that its values passed through an
    # RGB colorspace, this is set to the class for said RGB color space.
    # Allows reversing conversions automatically and accurately.
    _through_rgb_type = None

    def get_value_tuple(self):
        """
        Returns a tuple of the color's values (in order). For example,
        an LabColor object will return (lab_l, lab_a, lab_b), where each
        member of the tuple is the float value for said variable.
        """
        retval = tuple()
        for val in self.VALUES:
            retval += (getattr(self, val),)
        return retval

    def __str__(self):
        """
        String representation of the color.
        """
        retval = self.__class__.__name__ + " ("
        for val in self.VALUES:
            value = getattr(self, val, None)
            if value is not None:
                retval += "%s:%.4f " % (val, getattr(self, val))
        if hasattr(self, "observer"):
            retval += "observer:" + self.observer
        if hasattr(self, "illuminant"):
            retval += " illuminant:" + self.illuminant
        return retval.strip() + ")"

    def __repr__(self):
        """
        Evaluable string representation of the object.
        """
        retval = self.__class__.__name__ + "("
        attributes = [(attr, getattr(self, attr)) for attr in self.VALUES]
        values = [x + "=" + repr(y) for x, y in attributes]
        retval += ", ".join(values)
        if hasattr(self, "observer"):
            retval += ", observer='" + self.observer + "'"
        if hasattr(self, "illuminant"):
            retval += ", illuminant='" + self.illuminant + "'"
        return retval + ")"

class BaseRGBColor(ColorBase):
    """
    Base class for all RGB color spaces.

    .. warning:: Do not use this class directly!
    """

    VALUES = ["rgb_r", "rgb_g", "rgb_b"]

    def __init__(self, rgb_r, rgb_g, rgb_b, is_upscaled=False):
        """
        :param float rgb_r: R coordinate. 0.0-1.0, or 0-255 if is_upscaled=True.
        :param float rgb_g: G coordinate. 0.0-1.0, or 0-255 if is_upscaled=True.
        :param float rgb_b: B coordinate. 0.0-1.0, or 0-255 if is_upscaled=True.
        :keyword bool is_upscaled: If False, RGB coordinate values are
            between 0.0 and 1.0. If True, RGB values are between 0 and 255.
        """
        super(BaseRGBColor, self).__init__()
        if is_upscaled:
            self.rgb_r = rgb_r / 255.0
            self.rgb_g = rgb_g / 255.0
            self.rgb_b = rgb_b / 255.0
        else:
            self.rgb_r = float(rgb_r)
            self.rgb_g = float(rgb_g)
            self.rgb_b = float(rgb_b)
        self.is_upscaled = is_upscaled

    def _clamp_rgb_coordinate(self, coord):
        """
        Clamps an RGB coordinate, taking into account whether or not the
        color is upscaled or not.

        :param float coord: The coordinate value.
        :rtype: float
        :returns: The clamped value.
        """
        if not self.is_upscaled:
            return min(max(coord, 0.0), 1.0)
        else:
            return min(max(coord, 0.0), 255.0)

    @property
    def clamped_rgb_r(self):
        """
        The clamped (0.0-1.0) R value.
        """
        return self._clamp_rgb_coordinate(self.rgb_r)

    @property
    def clamped_rgb_g(self):
        """
        The clamped (0.0-1.0) G value.
        """
        return self._clamp_rgb_coordinate(self.rgb_g)

    @property
    def clamped_rgb_b(self):
        """
        The clamped (0.0-1.0) B value.
        """
        return self._clamp_rgb_coordinate(self.rgb_b)

    def get_upscaled_value_tuple(self):
        """
        Scales an RGB color object from decimal 0.0-1.0 to int 0-255.
        """
        # Scale up to 0-255 values.
        rgb_r = int(math.floor(0.5 + self.rgb_r * 255))
        rgb_g = int(math.floor(0.5 + self.rgb_g * 255))
        rgb_b = int(math.floor(0.5 + self.rgb_b * 255))

        return rgb_r, rgb_g, rgb_b

    def get_rgb_hex(self):
        """
        Converts the RGB value to a hex value in the form of: #RRGGBB

        :rtype: str
        """
        rgb_r, rgb_g, rgb_b = self.get_upscaled_value_tuple()
        return "#%02x%02x%02x" % (rgb_r, rgb_g, rgb_b)

    @classmethod
    def new_from_rgb_hex(cls, hex_str):
        """
        Converts an RGB hex string like #RRGGBB and assigns the values to
        this sRGBColor object.

        :rtype: sRGBColor
        """
        colorstring = hex_str.strip()
        if colorstring[0] == "#":
            colorstring = colorstring[1:]
        if len(colorstring) != 6:
            raise ValueError("input #%s is not in #RRGGBB format" % colorstring)
        r, g, b = colorstring[:2], colorstring[2:4], colorstring[4:]
        r, g, b = [int(n, 16) / 255.0 for n in (r, g, b)]
        return cls(r, g, b)

class sRGBColor(BaseRGBColor):
    """
    Represents an sRGB color.

    .. note:: If you pass in upscaled values, we automatically scale them
        down to 0.0-1.0. If you need the old upscaled values, you can
        retrieve them with :py:meth:`get_upscaled_value_tuple`.

    :ivar float rgb_r: R coordinate
    :ivar float rgb_g: G coordinate
    :ivar float rgb_b: B coordinate
    :ivar bool is_upscaled: If True, RGB values are between 0-255. If False,
        0.0-1.0.
    """

    #: RGB space's gamma constant.
    rgb_gamma = 2.2
    #: The RGB space's native illuminant. Important when converting to XYZ.
    native_illuminant = "d65"
    conversion_matrices = {
        "xyz_to_rgb":[
                [3.24071, -1.53726, -0.498571],
                [-0.969258, 1.87599, 0.0415557],
                [0.0556352, -0.203996, 1.05707],
        ],
        "rgb_to_xyz":[
                [0.412424, 0.357579, 0.180464],
                [0.212656, 0.715158, 0.0721856],
                [0.0193324, 0.119193, 0.950444],
        ],
    }

class IlluminantMixin(object):
    """
    Color spaces that have a notion of an illuminant should inherit this.
    """

    # noinspection PyAttributeOutsideInit
    def set_observer(self, observer):
        """
        Validates and sets the color's observer angle.

        .. note:: This only changes the observer angle value. It does no conversion
            of the color's coordinates.

        :param str observer: One of '2' or '10'.
        """
        observer = str(observer)
        if observer not in color_constants.OBSERVERS:
            raise InvalidObserverError(self)
        self.observer = observer

    # noinspection PyAttributeOutsideInit
    def set_illuminant(self, illuminant):
        """
        Validates and sets the color's illuminant.

        .. note:: This only changes the illuminant. It does no conversion
            of the color's coordinates. For this, you'll want to refer to
            :py:meth:`XYZColor.apply_adaptation \
<colormath.color_objects.XYZColor.apply_adaptation>`.

        .. tip:: Call this after setting your observer.

        :param str illuminant: One of the various illuminants.
        """
        illuminant = illuminant.lower()
        if illuminant not in color_constants.ILLUMINANTS[self.observer]:
            raise InvalidIlluminantError(illuminant)
        self.illuminant = illuminant

    def get_illuminant_xyz(self, observer=None, illuminant=None):
        """
        :param str observer: Get the XYZ values for another observer angle. Must
            be either '2' or '10'.
        :param str illuminant: Get the XYZ values for another illuminant.
        :returns: the color's illuminant's XYZ values.
        """
        try:
            if observer is None:
                observer = self.observer

            illums_observer = color_constants.ILLUMINANTS[observer]
        except KeyError:
            raise InvalidObserverError(self)

        try:
            if illuminant is None:
                illuminant = self.illuminant

            illum_xyz = illums_observer[illuminant]
        except (KeyError, AttributeError):
            raise InvalidIlluminantError(illuminant)

        return {"X": illum_xyz[0], "Y": illum_xyz[1], "Z": illum_xyz[2]}

class XYZColor(IlluminantMixin, ColorBase):
    """
    Represents an XYZ color.
    """

    VALUES = ["xyz_x", "xyz_y", "xyz_z"]

    def __init__(self, xyz_x, xyz_y, xyz_z, observer="2", illuminant="d50"):
        """
        :param float xyz_x: X coordinate.
        :param float xyz_y: Y coordinate.
        :param float xyz_z: Z coordinate.
        :keyword str observer: Observer angle. Either ``'2'`` or ``'10'`` degrees.
        :keyword str illuminant: See :doc:`illuminants` for valid values.
        """
        super(XYZColor, self).__init__()
        #: X coordinate
        self.xyz_x = float(xyz_x)
        #: Y coordinate
        self.xyz_y = float(xyz_y)
        #: Z coordinate
        self.xyz_z = float(xyz_z)

        #: The color's observer angle. Set with :py:meth:`set_observer`.
        self.observer = None
        #: The color's illuminant. Set with :py:meth:`set_illuminant`.
        self.illuminant = None

        self.set_observer(observer)
        self.set_illuminant(illuminant)

def apply_chromatic_adaptation(
    val_x, val_y, val_z, orig_illum, targ_illum, observer="2", adaptation="bradford"
):
    """
    Applies a chromatic adaptation matrix to convert XYZ values between
    illuminants. It is important to recognize that color transformation results
    in color errors, determined by how far the original illuminant is from the
    target illuminant. For example, D65 to A could result in very high maximum
    deviance.

    An informative article with estimate average Delta E values for each
    illuminant conversion may be found at:

    http://brucelindbloom.com/ChromAdaptEval.html
    """
    # It's silly to have to do this, but some people may want to call this
    # function directly, so we'll protect them from messing up upper/lower case.
    adaptation = adaptation.lower()

    # Get white-points for illuminant
    if isinstance(orig_illum, str):
        orig_illum = orig_illum.lower()
        wp_src = color_constants.ILLUMINANTS[observer][orig_illum]
    elif hasattr(orig_illum, "__iter__"):
        wp_src = orig_illum

    if isinstance(targ_illum, str):
        targ_illum = targ_illum.lower()
        wp_dst = color_constants.ILLUMINANTS[observer][targ_illum]
    elif hasattr(targ_illum, "__iter__"):
        wp_dst = targ_illum

    logger.debug("  \\* Applying adaptation matrix: %s", adaptation)
    # Retrieve the appropriate transformation matrix from the constants.
    transform_matrix = _get_adaptation_matrix(wp_src, wp_dst, observer, adaptation)

    # Stuff the XYZ values into a NumPy matrix for conversion.
    XYZ_matrix = numpy.array((val_x, val_y, val_z))
    # Perform the adaptation via matrix multiplication.
    result_matrix = numpy.dot(transform_matrix, XYZ_matrix)

    # Return individual X, Y, and Z coordinates.
    return result_matrix[0], result_matrix[1], result_matrix[2]



def apply_chromatic_adaptation_on_color(color, targ_illum, adaptation="bradford"):
    """
    Convenience function to apply an adaptation directly to a Color object.
    """
    xyz_x = color.xyz_x
    xyz_y = color.xyz_y
    xyz_z = color.xyz_z
    orig_illum = color.illuminant
    targ_illum = targ_illum.lower()
    observer = color.observer
    adaptation = adaptation.lower()

    # Return individual X, Y, and Z coordinates.
    color.xyz_x, color.xyz_y, color.xyz_z = apply_chromatic_adaptation(
        xyz_x,
        xyz_y,
        xyz_z,
        orig_illum,
        targ_illum,
        observer=observer,
        adaptation=adaptation,
    )
    color.set_illuminant(targ_illum)

    return color

    def apply_adaptation(self, target_illuminant, adaptation="bradford"):
        """
        This applies an adaptation matrix to change the XYZ color's illuminant.
        You'll most likely only need this during RGB conversions.
        """
        logger.debug("  \\- Original illuminant: %s", self.illuminant)
        logger.debug("  \\- Target illuminant: %s", target_illuminant)

        # If the XYZ values were taken with a different reference white than the
        # native reference white of the target RGB space, a transformation matrix
        # must be applied.
        if self.illuminant != target_illuminant:
            logger.debug(
                "  \\* Applying transformation from %s to %s ",
                self.illuminant,
                target_illuminant,
            )
            # Sets the adjusted XYZ values, and the new illuminant.
            apply_chromatic_adaptation_on_color(
                color=self, targ_illum=target_illuminant, adaptation=adaptation
            )


_conversion_manager = GraphConversionManager()

def convert_color(
    color,
    target_cs,
    through_rgb_type=sRGBColor,
    target_illuminant=None,
    *args,
    **kwargs
):
    """
    Converts the color to the designated color space.

    :param color: A Color instance to convert.
    :param target_cs: The Color class to convert to. Note that this is not
        an instance, but a class.
    :keyword BaseRGBColor through_rgb_type: If during your conversion between
        your original and target color spaces you have to pass through RGB,
        this determines which kind of RGB to use. For example, XYZ->HSL.
        You probably don't need to specify this unless you have a special
        usage case.
    :type target_illuminant: None or str
    :keyword target_illuminant: If during conversion from RGB to a reflective
        color space you want to explicitly end up with a certain illuminant,
        pass this here. Otherwise the RGB space's native illuminant
        will be used.
    :returns: An instance of the type passed in as ``target_cs``.
    :raises: :py:exc:`colormath.color_exceptions.UndefinedConversionError`
        if conversion between the two color spaces isn't possible.
    """
    if isinstance(target_cs, str):
        raise ValueError("target_cs parameter must be a Color object.")
    if not issubclass(target_cs, ColorBase):
        raise ValueError("target_cs parameter must be a Color object.")

    conversions = _conversion_manager.get_conversion_path(color.__class__, target_cs)

    logger.debug("Converting %s to %s", color, target_cs)
    logger.debug(" @ Conversion path: %s", conversions)

    # Start with original color in case we convert to the same color space.
    new_color = color

    if issubclass(target_cs, BaseRGBColor):
        # If the target_cs is an RGB color space of some sort, then we
        # have to set our through_rgb_type to make sure the conversion returns
        # the expected RGB colorspace (instead of defaulting to sRGBColor).
        through_rgb_type = target_cs

    # We have to be careful to use the same RGB color space that created
    # an object (if it was created by a conversion) in order to get correct
    # results. For example, XYZ->HSL via Adobe RGB should default to Adobe
    # RGB when taking that generated HSL object back to XYZ.
    # noinspection PyProtectedMember
    if through_rgb_type != sRGBColor:
        # User overrides take priority over everything.
        # noinspection PyProtectedMember
        target_rgb = through_rgb_type
    elif color._through_rgb_type:
        # Otherwise, a value on the color object is the next best thing,
        # when available.
        # noinspection PyProtectedMember
        target_rgb = color._through_rgb_type
    else:
        # We could collapse this into a single if statement above,
        # but I think this reads better.
        target_rgb = through_rgb_type

    # Iterate through the list of functions for the conversion path, storing
    # the results in a dictionary via update(). This way the user has access
    # to all of the variables involved in the conversion.
    for func in conversions:
        # Execute the function in this conversion step and store the resulting
        # Color object.
        logger.debug(
            " * Conversion: %s passed to %s()", new_color.__class__.__name__, func
        )
        logger.debug(" |->  in %s", new_color)

        if func:
            # This can be None if you try to convert a color to the color
            # space that is already in. IE: XYZ->XYZ.
            new_color = func(
                new_color,
                target_rgb=target_rgb,
                target_illuminant=target_illuminant,
                *args,
                **kwargs
            )

        logger.debug(" |-< out %s", new_color)

    # If this conversion had something other than the default sRGB color space
    # requested,
    if through_rgb_type != sRGBColor:
        new_color._through_rgb_type = through_rgb_type

    return new_color