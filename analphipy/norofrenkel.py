import numpy as np

from .measures import secondvirial, secondvirial_dbeta, secondvirial_sw
from .utils import TWO_PI, minimize_phi, quad_segments


def add_quad_kws(func):
    def wrapped(self, *args, **kws):
        kws = dict(self.quad_kws, **kws)
        return func(self, *args, **kws)

    return wrapped


def sig_nf(phi_rep, beta, segments, err=False, full_output=False, **kws):
    """Noro-Frenkel/Barker-Henderson effective hard sphere diameter"""

    def integrand(r):
        return 1.0 - np.exp(-beta * phi_rep(r))

    return quad_segments(
        integrand,
        segments=segments,
        sum_integrals=True,
        sum_errors=True,
        err=err,
        full_output=full_output,
        **kws
    )


def sig_nf_dbeta(phi_rep, beta, segments, err=False, full_output=False, **kws):
    """derivative w.r.t. beta of sig_nf"""

    def integrand(r):
        v = phi_rep(r)
        if np.isinf(v):
            return 0.0
        else:
            return v * np.exp(-beta * v)

    return quad_segments(
        integrand,
        segments=segments,
        sum_integrals=True,
        sum_errors=True,
        err=err,
        full_output=full_output,
        **kws
    )


def lam_nf(beta, sig, eps, B2):
    B2star = B2 / (TWO_PI / 3.0 * sig ** 3)

    # B2s_SW = 1 + (1-exp(-beta epsilon)) * (lambda**3 - 1)
    #        = B2s
    lam = ((B2star - 1.0) / (1.0 - np.exp(-beta * eps)) + 1.0) ** (1.0 / 3.0)
    return lam


def lam_nf_dbeta(beta, sig, eps, lam, B2, B2_dbeta, sig_dbeta):
    """
    calculate d(lam_nf)/d(beta) from known parameters
    Parameters
    ----------
    beta : float
        inverse temperature
    sig, eps, lam : float
        Noro-frenkel sigma/eps/lambda parameters
    B2 : float
        Actual second virial coef
    B2_dbeta : float
        d(B2)/d(beta) at `beta`
    sig_dbeta : float
        derivative of noro-frenkel sigma w.r.t inverse temperature at `beta`
    """

    B2_hs = TWO_PI / 3.0 * sig ** 3

    dB2stardbeta = 1.0 / B2_hs * (B2_dbeta - B2 * 3.0 * sig_dbeta / sig)

    # e = np.exp(-beta * eps)
    # f = 1. - e

    e = np.exp(beta * eps)

    out = 1.0 / (3 * lam ** 2 * (e - 1)) * (dB2stardbeta * e - eps * (lam ** 3 - 1))

    return out


class NoroFrenkelPair:
    def __init__(self, phi, segments, x_min, phi_min, quad_kws=None):

        self.phi = phi
        self.x_min = x_min

        if phi_min is None:
            phi_min = phi(x_min)
        self.phi_min = phi_min
        self.segments = segments

        if quad_kws is None:
            quad_kws = {}
        self.quad_kws = {}

    def phi_rep(self, r):
        r = np.array(r)
        phi = np.empty_like(r)
        m = r <= self.x_min

        phi[m] = self.phi(r[m]) - self.phi_min
        phi[~m] = 0.0

        return phi

    @classmethod
    def from_phi(cls, phi, segments, bounds=None, xmin=None, quad_kws=None, **kws):
        xmin, phi_min, _ = minimize_phi(phi, r0=xmin, bounds=bounds, **kws)
        return cls(
            phi=phi, x_min=xmin, phi_min=phi_min, segments=segments, quad_kws=quad_kws
        )

    @add_quad_kws
    def secondvirial(self, beta, **kws):
        return secondvirial(phi=self.phi, beta=beta, segments=self.segments, **kws)

    @add_quad_kws
    def sig(self, beta, **kws):
        return sig_nf(self.phi_rep, beta=beta, segments=self.segments, **kws)

    def eps(self, beta, **kws):
        return self.phi_min

    @add_quad_kws
    def lam(self, beta, **kws):
        return lam_nf(
            beta=beta,
            sig=self.sig(beta, **kws),
            eps=self.eps(beta, **kws),
            B2=self.secondvirial(beta, **kws),
        )

    @add_quad_kws
    def secondvirial_dbeta(self, beta, **kws):
        return secondvirial_dbeta(
            phi=self.phi, beta=beta, segments=self.segments, **kws
        )

    @add_quad_kws
    def sig_dbeta(self, beta, **kws):
        return sig_nf_dbeta(self.phi_rep, beta=beta, segments=self.segments, **kws)

    def lam_dbeta(self, beta, **kws):
        return lam_nf_dbeta(
            beta=beta,
            sig=self.sig(beta, **kws),
            eps=self.eps(beta, **kws),
            lam=self.lam(beta, **kws),
            B2=self.secondvirial(beta, **kws),
            B2_dbeta=self.secondvirial_dbeta(beta, **kws),
            sig_dbeta=self.sig_dbeta(beta, **kws),
        )

    def secondvirial_sw(self, beta, **kws):
        return secondvirial_sw(
            beta=beta,
            sig=self.sig(beta, **kws),
            eps=self.eps(beta, **kws),
            lam=self.lam(beta, **kws),
        )

    def B2(self, beta, **kws):
        return self.secondvirial(beta, **kws)

    def B2_dbeta(self, beta, **kws):
        return self.secondvirial_dbeta(beta, **kws)

    def table(self, betas, props=None, key_format="{prop}", **kws):
        if props is None:
            props = ["B2", "sig", "eps", "lam"]

        table = {"beta": betas}

        for prop in props:
            f = getattr(self, prop)
            key = key_format.format(prop=prop)
            table[key] = [f(beta=beta, **kws) for beta in betas]

        return table
