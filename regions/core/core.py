# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import abc
import operator
import weakref

from astropy.extern import six
from astropy.coordinates import SkyCoord
from astropy.units import Quantity
import numpy as np


__all__ = ['Region', 'PixelRegion', 'SkyRegion', 'RegionMeta', 'RegionVisual']


"""
Here we define global variables for the default `origin` and `mode` used
for WCS transformations throughout the `regions` package.

Their purpose is to simplify achieving uniformity across the codebase.
They are mainly used as default arguments for methods that do WCS
transformations.

They are private (with an underscore), not part of the public API,
users should not touch them.
"""
_DEFAULT_WCS_ORIGIN = 0
_DEFAULT_WCS_MODE = 'all'

VALID_MASK_MODES = {'center', 'exact', 'subpixels'}

from .pixcoord import PixCoord


@six.add_metaclass(abc.ABCMeta)
class Region(object):
    """
    Base class for all regions.
    """

    def __repr__(self):
        if hasattr(self, 'center'):
            params = [repr(self.center)]
        else:
            params = []
        if self._repr_params is not None:
            for key in self._repr_params:
                params.append('{0}={1}'.format(key.replace("_", " "),
                                               getattr(self, key)))
        params = ', '.join(params)

        return '<{0}({1})>'.format(self.__class__.__name__, params)

    def __str__(self):
        cls_info = [('Region', self.__class__.__name__)]
        if hasattr(self, 'center'):
            cls_info.append(('center', self.center))
        if self._repr_params is not None:
            params_value = [(x.replace("_", " "), getattr(self, x))
                            for x in self._repr_params]
            cls_info += params_value
        fmt = ['{0}: {1}'.format(key, val) for key, val in cls_info]

        return '\n'.join(fmt)

    @abc.abstractmethod
    def intersection(self, other):
        """
        Returns a region representing the intersection of this region with
        ``other``.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def symmetric_difference(self, other):
        """
        Returns the union of the two regions minus any areas contained in the
        intersection of the two regions.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def union(self, other):
        """
        Returns a region representing the union of this region with ``other``.
        """
        raise NotImplementedError

    def __and__(self, other):
        return self.intersection(other)

    def __or__(self, other):
        return self.union(other)

    def __xor__(self, other):
        return self.symmetric_difference(other)


@six.add_metaclass(abc.ABCMeta)
class PixelRegion(Region):
    """
    Base class for all regions defined in pixel coordinates
    """

    def intersection(self, other):
        """
        Returns a region representing the intersection of this region with
        ``other``.
        """
        from .compound import CompoundPixelRegion
        return CompoundPixelRegion(region1=self, region2=other, operator=operator.and_)

    def symmetric_difference(self, other):
        """
        Returns the union of the two regions minus any areas contained in the
        intersection of the two regions.
        """
        from .compound import CompoundPixelRegion
        return CompoundPixelRegion(region1=self, region2=other, operator=operator.xor)

    def union(self, other):
        """
        Returns a region representing the union of this region with ``other``.
        """
        from .compound import CompoundPixelRegion
        return CompoundPixelRegion(region1=self, region2=other, operator=operator.or_)

    @abc.abstractmethod
    def contains(self, pixcoord):
        """
        Checks whether a position or positions fall inside the region.

        Parameters
        ----------
        pixcoord : `~regions.PixCoord`
            The position or positions to check, as a tuple of scalars or
            arrays. In future this could also be a `PixCoord` instance.
        """
        raise NotImplementedError

    def __contains__(self, coord):
        if not coord.isscalar:
            raise ValueError('coord must be scalar. coord={}'.format(coord))
        return self.contains(coord)

    @abc.abstractmethod
    def to_sky(self, wcs):
        """
        Returns a region defined in sky coordinates.

        Parameters
        ----------
        wcs : `~astropy.wcs.WCS` instance
            The world coordinate system transformation to assume
        """
        raise NotImplementedError

    @abc.abstractproperty
    def bounding_box(self):
        """
        The minimal bounding box (in integer pixel coordinates) that contains
        the region.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def to_mask(self, mode='center', subpixels=5):
        """
        Returns a mask for the aperture.

        Parameters
        ----------
        mode : { 'center' | 'exact' | 'subpixels'}
            The following modes are available:
                * ``'center'``: returns 1 for pixels where the center is in
                  the region, and 0 otherwise.
                * ``'exact'``: returns a value between 0 and 1 giving the
                  fractional level of overlap of the pixel with the region.
                * ``'subpixels'``: A pixel is divided into subpixels and
                  the center of each subpixel is tested (a subpixel is
                  either completely in or out of the region).  Returns a
                  value between 0 and 1 giving the fractional level of
                  overlap of the subpixels with the region.  With
                  ``subpixels`` set to 1, this method is equivalent to
                  ``'center'``.
        subpixels : int, optional
            For the ``'subpixel'`` mode, resample pixels by this factor
            in each dimension. That is, each pixel is divided into
            ``subpixels ** 2`` subpixels.

        Returns
        -------
        mask : `~regions.Mask`
            A region mask object.
        """
        raise NotImplementedError

    @staticmethod
    def _validate_mode(mode, subpixels):
        if mode not in VALID_MASK_MODES:
            raise ValueError("Invalid mask mode: {0} (should be one "
                             "of {1})".format(mode, '/'.join(VALID_MASK_MODES)))
        if mode == 'subpixels':
            if not isinstance(subpixels, int) or subpixels <= 0:
                raise ValueError("Invalid subpixels value: {0} (should be"
                                 " a strictly positive integer)".format(subpixels))

    @abc.abstractmethod
    def to_shapely(self):
        """
        Convert this region to a Shapely object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def as_patch(self, **kwargs):
        """Convert to mpl patch

        Returns
        -------
        patch : `~matplotlib.patches.Patch`
            Matplotlib patch
        """
        raise NotImplementedError

    def plot(self, ax=None, **kwargs):
        """
        Calls as_patch method forwarding all kwargs and adds patch
        to given axis.

        Parameters
        ----------
        ax : `~matplotlib.axes`, optional
            Axis
        """
        import matplotlib.pyplot as plt

        if ax is None:
            ax = plt.gca()

        patch = self.as_patch(**kwargs)
        ax.add_patch(patch)

        return ax


@six.add_metaclass(abc.ABCMeta)
class SkyRegion(Region):
    """
    Base class for all regions defined in celestial coordinates
    """

    def intersection(self, other):
        """
        Returns a region representing the intersection of this region with
        ``other``.
        """
        from .compound import CompoundSkyRegion
        return CompoundSkyRegion(region1=self, region2=other, operator=operator.and_)

    def symmetric_difference(self, other):
        """
        Returns the union of the two regions minus any areas contained in the
        intersection of the two regions.
        """
        from .compound import CompoundSkyRegion
        return CompoundSkyRegion(region1=self, region2=other, operator=operator.xor)

    def union(self, other):
        """
        Returns a region representing the union of this region with ``other``.
        """
        from .compound import CompoundSkyRegion
        return CompoundSkyRegion(region1=self, region2=other, operator=operator.or_)

    def contains(self, skycoord, wcs):
        """
        Check whether a sky coordinate falls inside the region

        Parameters
        ----------
        skycoord : `~astropy.coordinates.SkyCoord`
            The position or positions to check
        wcs : `~astropy.wcs.WCS` instance
            The world coordinate system transformation to assume
        """
        from .pixcoord import PixCoord
        pixel_region = self.to_pixel(wcs)
        pixcoord = PixCoord.from_sky(skycoord, wcs)
        return pixel_region.contains(pixcoord)

    @abc.abstractmethod
    def to_pixel(self, wcs):
        """
        Returns the equivalent region defined in pixel coordinates.

        Parameters
        ----------
        wcs : `~astropy.wcs.WCS` instance
            The world coordinate system transformation to assume
        """
        raise NotImplementedError


@six.add_metaclass(abc.ABCMeta)
class RegionAttr(object):

    def __init__(self, name):
        self._name = name
        self._values = weakref.WeakKeyDictionary()

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self._values.get(instance, None)

    def __set__(self, instance, value):
        self._validate(value)
        self._values[instance] = value

    def _validate(self, value):
        raise NotImplementedError


class ScalarPix(RegionAttr):

    def _validate(self, value):
        if not(isinstance(value, PixCoord) and value.isscalar):
            raise ValueError('The {} must be a 0D PixCoord object'
                             .format(self._name))


class OneDPix(RegionAttr):

    def _validate(self, value):
        if not(isinstance(value, PixCoord) and not value.isscalar
               and value.x.ndim == 1):
            raise ValueError('The {} must be a 1D PixCoord object'
                             .format(self._name))


class AnnulusCenterPix(object):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg1 = getattr(instance, 'region1')
        return getattr(reg1, 'center')

    def __set__(self, instance, value):

        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if isinstance(value, PixCoord) and value.isscalar:
            setattr(reg1, 'center', value)
            setattr(reg2, 'center', value)
        else:
            raise ValueError('The center must be a 0D PixCoord object')


class ScalarLength(RegionAttr):

    def _validate(self, value):
        if not np.isscalar(value):
            raise ValueError(
                'The {} must be a scalar numpy/python number'.format(self._name))


class AnnulusInnerScalarLength(object):

    def __init__(self, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg1 = getattr(instance, 'region1')
        return getattr(reg1, self._name)

    def __set__(self, instance, value):
        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if np.isscalar(value):
            if getattr(reg2, self._name) < value:
                raise ValueError("The inner {0} must be less than the outer {0}"
                                .format(self._name)
                             )
            else:
                setattr(reg1, self._name, value)
        else:
            raise ValueError('The inner {} must be a scalar numpy/python number'
                             .format(self._name))


class AnnulusOuterScalarLength(object):

    def __init__(self, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg2 = getattr(instance, 'region2')
        return getattr(reg2, self._name)

    def __set__(self, instance, value):
        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if np.isscalar(value):
            if getattr(reg1, self._name) > value:
                raise ValueError("The outer {0} must be greater than the outer"
                                 " {0}".format(self._name)
                                 )
            else:
                setattr(reg2, self._name, value)
        else:
            raise ValueError('The outer {} must be a scalar numpy/python number'
                             .format(self._name))


class ScalarSky(RegionAttr):

    def _validate(self, value):
        if not(isinstance(value, SkyCoord) and value.isscalar):
            raise ValueError('The {} must be a 0D SkyCoord object'.
                             format(self._name))


class OneDSky(RegionAttr):

    def _validate(self, value):
        if not(isinstance(value, SkyCoord) and value.ndim == 1):
            raise ValueError('The {} must be a 1D SkyCoord object'.
                             format(self._name))


class AnnulusCenterSky(object):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg1 = getattr(instance, 'region1')
        return getattr(reg1, 'center')

    def __set__(self, instance, value):

        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if isinstance(value, SkyCoord) and value.isscalar:
            setattr(reg1, 'center', value)
            setattr(reg2, 'center', value)
        else:
            raise ValueError('The center must be a 0D SkyCoord object')


class QuantityLength(RegionAttr):

    def _validate(self, value):
        if not(isinstance(value, Quantity) and value.isscalar):
            raise ValueError('The {} must be a scalar astropy Quantity object'
                             .format(self._name))


class AnnulusInnerQuantityLength(object):

    def __init__(self, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg1 = getattr(instance, 'region1')
        return getattr(reg1, self._name)

    def __set__(self, instance, value):
        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if isinstance(value, Quantity) and value.isscalar:
            if getattr(reg2, self._name) < value:
                raise ValueError("The inner {0} must be less than the outer {0}"
                                 .format(self._name)
                                 )
            else:
                setattr(reg1, self._name, value)
        else:
            raise ValueError('The inner {} must be a scalar astropy Quantity '
                             'object'.format(self._name))


class AnnulusOuterQuantityLength(object):

    def __init__(self, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg2 = getattr(instance, 'region2')
        return getattr(reg2, self._name)

    def __set__(self, instance, value):
        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if isinstance(value, Quantity) and value.isscalar:
            if getattr(reg1, self._name) > value:
                raise ValueError("The inner {0} must be less than the outer {0}"
                                 .format(self._name)
                                 )
            else:
                setattr(reg2, self._name, value)
        else:
            raise ValueError('The outer {} must be a scalar astropy Quantity '
                             'object'.format(self._name))


class AnnulusAngle(object):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        reg1 = getattr(instance, 'region1')
        return getattr(reg1, 'angle')

    def __set__(self, instance, value):

        reg1 = getattr(instance, 'region1')
        reg2 = getattr(instance, 'region2')

        if isinstance(value, Quantity) and value.isscalar:
            setattr(reg1, 'angle', value)
            setattr(reg2, 'angle', value)
        else:
            raise ValueError('The angle must be a scalar astropy quantity object')


class CompoundRegionPix(RegionAttr):

    def _validate(self, value):
        if not isinstance(value, PixelRegion):
            raise ValueError('The {} must be a PixelRegion object'
                             .format(self._name))


class CompoundRegionSky(RegionAttr):

    def _validate(self, value):
        if not isinstance(value, SkyRegion):
            raise ValueError('The {} must be a SkyRegion object'
                             .format(self._name))


class RegionMeta(dict):
    """
    A python dictionary subclass which holds the meta attributes of the region.
    """
    valid_keys = ['label', 'symbol', 'include', 'frame', 'range', 'veltype',
                  'restfreq', 'tag', 'comment', 'coord', 'line', 'name',
                  'select', 'highlite', 'fixed', 'edit', 'move', 'rotate',
                  'delete', 'source', 'background', 'corr', 'type'
                  ]

    key_mapping = {'point': 'symbol', 'text': 'label'}

    def __setitem__(self, key, value):
        key = self.key_mapping.get(key, key)
        if key in self.valid_keys:
            super(RegionMeta, self).__setitem__(key, value)
        else:
            raise KeyError("{} is not a valid meta key for region.".format(key))

    def __getitem__(self, item):
        item = self.key_mapping.get(item, item)
        return super(RegionMeta, self).__getitem__(item)


class RegionVisual(dict):
    """
    A python dictionary subclass which holds the visual attributes of the region.
    """
    valid_keys = ['color', 'dash', 'font', 'dashlist', 'symsize', 'symthick',
                  'fontsize', 'fontstyle', 'usetex', 'labelpos', 'labeloff',
                  'linewidth', 'linestyle', 'fill', 'line']

    key_mapping = {'width': 'linewidth'}

    def __setitem__(self, key, value):
        key = self.key_mapping.get(key, key)
        if key in self.valid_keys:
            super(RegionVisual, self).__setitem__(key, value)
        else:
            raise KeyError("{} is not a valid visual meta key for region.".format(key))

    def __getitem__(self, item):
        item = self.key_mapping.get(item, item)
        return super(RegionVisual, self).__getitem__(item)
