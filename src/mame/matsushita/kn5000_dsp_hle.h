// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
//
// upd6383_hle.h -- HLE REFERENCE kernels for the NEC uPD6383GF effects DSP, in C++.
//
// ⚠ THIS IS THE HLE REFERENCE, NOT THE LLE CORE.  It reproduces the transfer function / block
// diagram of each decoded effect kernel (biquad, one-pole, LFO, delay, waveshaper), a faithful
// C++ port of the validated Python reference (kn5000-roms-disasm dsp/hle/kernels.py).  It has NO
// dependency on the execution core (upd6383.cpp) and executes no microcode.  It exists so the
// eventual MAME HLE audio path can consume a single, offline-golden-anchored kernel set, and so
// the C++ and Python references can be diffed to 0.000 dB (upd6383_hle_test.cpp).
//
// double precision throughout, to match the Python float64 reference.

#ifndef KN5000_UPD6383_HLE_H
#define KN5000_UPD6383_HLE_H

#include <cmath>
#include <complex>
#include <vector>

namespace upd6383_hle {

// Direct-Form-I biquad, exactly the parametric-EQ band decoded to the bit (biquad-eq.md):
//   y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2], then * makeup.
class BiquadDF1
{
public:
	BiquadDF1(double b0, double b1, double b2, double a1, double a2, double makeup = 1.0)
		: m_b0(b0), m_b1(b1), m_b2(b2), m_a1(a1), m_a2(a2), m_mk(makeup) {}

	// Default = a unity passthrough (b0=1, everything else 0), so consumers can hold
	// an array of bands and load coefficients later via set_coeffs().
	BiquadDF1() : m_b0(1.0), m_b1(0.0), m_b2(0.0), m_a1(0.0), m_a2(0.0), m_mk(1.0) {}

	void reset() { m_x1 = m_x2 = m_y1 = m_y2 = 0.0; }

	// Reload the coefficients WITHOUT clearing the z^-1 state (so a live coefficient
	// refresh between stream updates does not click). MAME-port convenience.
	void set_coeffs(double b0, double b1, double b2, double a1, double a2, double makeup = 1.0)
	{ m_b0 = b0; m_b1 = b1; m_b2 = b2; m_a1 = a1; m_a2 = a2; m_mk = makeup; }

	double process_one(double x)
	{
		double y = m_b0 * x + m_b1 * m_x1 + m_b2 * m_x2 - m_a1 * m_y1 - m_a2 * m_y2;
		m_x2 = m_x1; m_x1 = x;
		m_y2 = m_y1; m_y1 = y;
		return y * m_mk;
	}

	// analytic magnitude response |H(e^jw)| * makeup at frequency f (Hz), sample rate fs.
	double response(double f, double fs) const
	{
		const double w = 2.0 * M_PI * f / fs;
		const std::complex<double> z1 = std::exp(std::complex<double>(0.0, -w));
		const std::complex<double> z2 = std::exp(std::complex<double>(0.0, -2.0 * w));
		const std::complex<double> H =
			(m_b0 + m_b1 * z1 + m_b2 * z2) / (1.0 + m_a1 * z1 + m_a2 * z2);
		return std::abs(H) * m_mk;
	}

private:
	double m_b0, m_b1, m_b2, m_a1, m_a2, m_mk;
	double m_x1 = 0.0, m_x2 = 0.0, m_y1 = 0.0, m_y2 = 0.0;
};

// One-pole low-pass loss (the reverb/mod damping, ACT 0x0D/0x0E pair): y = (1-d)x + d*y1.
class OnePole
{
public:
	explicit OnePole(double damping = 0.0) : m_d(damping) {}
	void reset() { m_y1 = 0.0; }
	double process_one(double x) { m_y1 = (1.0 - m_d) * x + m_d * m_y1; return m_y1; }
private:
	double m_d;
	double m_y1 = 0.0;
};

// LFO phase accumulator -> shaped table (the 0x092 word), phase in cycles [0,1).
class LFO
{
public:
	enum shape_t { SINE, TRIANGLE, SQUARE };
	LFO(double rate_hz, double fs, shape_t shape = SINE, double phase = 0.0)
		: m_inc(rate_hz / fs), m_shape(shape), m_phase(std::fmod(phase, 1.0)) {}
	double next()
	{
		const double ph = m_phase;
		m_phase = std::fmod(m_phase + m_inc, 1.0);
		switch (m_shape)
		{
		case SINE:     return std::sin(2.0 * M_PI * ph);
		case TRIANGLE: return 2.0 * std::fabs(2.0 * (ph - std::floor(ph + 0.5))) - 1.0;
		case SQUARE:   return ph < 0.5 ? 1.0 : -1.0;
		}
		return 0.0;
	}
private:
	double m_inc;
	shape_t m_shape;
	double m_phase;
};

// Delay line with fractional read (the delay-descriptor tap).
class DelayLine
{
public:
	explicit DelayLine(int max_samples) : m_buf(max_samples > 1 ? max_samples : 2, 0.0) {}
	void write(double x) { m_buf[m_head] = x; m_head = (m_head + 1) % int(m_buf.size()); }
	double read(double delay_samples) const
	{
		const int n = int(m_buf.size());
		double rp = double(m_head) - 1.0 - delay_samples;
		while (rp < 0.0) rp += n;
		const int i0 = int(rp) % n;
		const int i1 = (i0 + 1) % n;
		const double frac = rp - std::floor(rp);
		return m_buf[i0] * (1.0 - frac) + m_buf[i1] * frac;
	}
private:
	std::vector<double> m_buf;
	int m_head = 0;
};

// Soft-clip waveshaper (distortion), tanh curve at a given drive.
inline double waveshape(double x, double drive) { return std::tanh(drive * x); }

} // namespace upd6383_hle

#endif // KN5000_UPD6383_HLE_H
