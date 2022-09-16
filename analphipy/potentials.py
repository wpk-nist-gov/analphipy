from __future__ import annotations

# import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

# from functools import partial
from typing import Optional, Sequence, Tuple, cast

import numpy as np
from typing_extensions import Literal

from ._potentials import Phi_Abstractclass, Phi_Baseclass
from ._typing import Float_or_ArrayLike

# classes to handle pair potentials


@dataclass
class Phi_lj(Phi_Baseclass):
    sig: float = 1.0
    eps: float = 1.0

    def __post_init__(self):
        sig, eps = self.sig, self.eps
        self.sigsq = sig * sig
        self.four_eps = 4.0 * eps

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:
        r = np.array(r)
        x2 = self.sigsq / (r * r)
        x6 = x2**3
        return cast(np.ndarray, self.four_eps * x6 * (x6 - 1.0))

    def phidphi(self, r: Float_or_ArrayLike) -> tuple[np.ndarray, np.ndarray]:
        """calculate phi and dphi (=-1/r dphi/dr) at particular r"""
        r = np.array(r)
        rinvsq = 1.0 / (r * r)

        x2 = self.sigsq * rinvsq
        x6 = x2 * x2 * x2

        phi = self.four_eps * x6 * (x6 - 1.0)
        dphi = 12.0 * self.four_eps * x6 * (x6 - 0.5) * rinvsq
        return phi, dphi

    @property
    def r_min(self) -> float:
        return cast(float, self.sig * 2.0 ** (1.0 / 6.0))

    @property
    def phi_min(self) -> float:
        return -self.eps

    @property
    def segments(self):
        return [0.0, np.inf]


@dataclass
class Phi_nm(Phi_Baseclass):
    n: int = 12
    m: int = 6
    sig: float = 1.0
    eps: float = 1.0

    def __post_init__(self):
        n, m, eps = self.n, self.m, self.eps
        self.prefac = eps * (n / (n - m)) * (n / m) ** (m / (n - m))

    @property
    def r_min(self) -> float:
        n, m = self.n, self.m
        return cast(float, self.sig * (n / m) ** (1.0 / (n - m)))

    @property
    def phi_min(self) -> float:
        return -self.eps

    @property
    def segments(self):
        return [0.0, np.inf]

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:
        r = np.array(r)

        x = self.sig / r
        out = self.prefac * (x**self.n - x**self.m)
        return cast(np.ndarray, out)

    def phidphi(self, r: Float_or_ArrayLike) -> tuple[np.ndarray, np.ndarray]:

        r = np.array(r)
        x = self.sig / r

        xn = x**self.n
        xm = x**self.m

        phi = np.empty_like(r)
        dphi = np.empty_like(r)

        phi = self.prefac * (xn - xm)

        # dphi = -1/r dphi/dr = x dphi/dx * 1/r**2
        # where x = sig / r
        dphi = self.prefac * (self.n * xn - self.m * xm) / (r**2)

        return cast(Tuple[np.ndarray, np.ndarray], (phi, dphi))


@dataclass
class Phi_yk(Phi_Baseclass):

    z: float = 1.0
    sig: float = 1.0
    eps: float = 1.0

    @property
    def segments(self) -> list:
        return [0.0, self.sig, np.inf]

    @property
    def r_min(self) -> float:
        return self.sig

    @property
    def phi_min(self) -> float:
        return -self.eps

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:
        sig, eps = self.sig, self.eps

        r = np.array(r)
        phi = np.empty_like(r)
        m = r >= sig

        phi[~m] = np.inf
        if np.any(m):
            x = r[m] / sig
            phi[m] = -eps * np.exp(-self.z * (x - 1.0)) / x
        return phi


@dataclass
class Phi_hs(Phi_Baseclass):
    sig: float = 1.0

    @property
    def segments(self):
        return [0.0, self.sig]

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:
        r = np.array(r)

        phi = np.empty_like(r)

        m0 = r < self.sig
        phi[m0] = np.inf
        phi[~m0] = 0.0
        return phi


@dataclass
class Phi_sw(Phi_Baseclass):
    sig: float = 1.0
    eps: float = 1.0
    lam: float = 1.5

    @property
    def r_min(self) -> float:
        return self.sig

    @property
    def phi_min(self) -> float:
        return self.eps

    @property
    def segments(self) -> list:
        return [0.0, self.sig, self.sig * self.lam]

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:

        sig, eps, lam = self.sig, self.eps, self.lam

        r = np.array(r)

        phi = np.empty_like(r)

        m0 = r < sig
        m2 = r >= lam * sig
        m1 = (~m0) & (~m2)

        phi[m0] = np.inf
        phi[m1] = eps
        phi[m2] = 0.0

        return phi


class CubicTable(Phi_Baseclass):
    def __init__(self, bounds: Sequence[float], phi_array: Float_or_ArrayLike):

        self.phi_array = np.asarray(phi_array)
        self.bounds = bounds

        self.ds = (self.bounds[1] - self.bounds[0]) / self.size
        self.dsinv = 1.0 / self.ds

    @property
    def segments(self):
        return [np.sqrt(x) for x in self.bounds]

    @classmethod
    def from_phi(cls, phi: Callable, rmin: float, rmax: float, ds: float):
        bounds = (rmin * rmin, rmax * rmax)

        delta = bounds[1] - bounds[0]

        size = int(delta / ds)
        ds = delta / size

        phi_array = []

        r = np.sqrt(np.arange(size + 1) * ds + bounds[0])

        phi_array = phi(r)

        return cls(bounds=bounds, phi_array=phi_array)

    def __len__(self):
        return len(self.phi_array)

    @property
    def size(self) -> int:
        return len(self) - 1

    @property
    def smin(self) -> float:
        return self.bounds[0]

    @property
    def smax(self) -> float:
        return self.bounds[1]

    def phidphi(self, r: Float_or_ArrayLike) -> tuple[np.ndarray, np.ndarray]:
        r = np.asarray(r)

        v = np.empty_like(r)
        dv = np.empty_like(r)

        s = r * r
        left = s <= self.smax
        right = ~left

        v[right] = 0.0
        dv[right] = 0.0

        if np.any(left):

            sds = (s[left] - self.smin) * self.dsinv
            k = sds.astype(int)
            k[k < 0] = 0

            xi = sds - k

            t = np.take(self.phi_array, [k, k + 1, k + 2], mode="clip")
            dt = np.diff(t, axis=0)
            ddt = np.diff(dt, axis=0)

            v[left] = t[0, :] + xi * (dt[0, :] + 0.5 * (xi - 1.0) * ddt[0, :])
            dv[left] = -2.0 * self.dsinv * (dt[0, :] + (xi - 0.5) * ddt[0, :])

        return v, dv

    def phi(self, r: Float_or_ArrayLike) -> np.ndarray:
        return self.phidphi(r)[0]


_PHI_NAMES = Literal["lj", "nm", "sw", "hs", "yk", "LJ", "NM", "SW", "HS", "YK"]


def factory_phi(
    potential_name: _PHI_NAMES,
    rcut: Optional[float] = None,
    lfs: bool = False,
    cut: bool = False,
    **kws,
) -> Phi_Abstractclass:

    name = potential_name.lower()

    phi: Phi_Abstractclass

    if name == "lj":
        phi = Phi_lj(**kws)

    elif name == "sw":
        phi = Phi_sw(**kws)

    elif name == "nm":
        phi = Phi_nm(**kws)

    elif name == "yk":
        phi = Phi_yk(**kws)

    elif name == "hs":
        phi = Phi_hs(**kws)

    else:
        raise ValueError(f"{name} must be in {_PHI_NAMES}")

    if lfs or cut:
        assert rcut is not None
        if cut:
            phi = phi.cut(rcut=rcut)

        elif lfs:
            phi = phi.lfs(rcut=rcut)

    return phi
