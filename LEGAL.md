← [Back to README](README.md)

# Legal basis for this research

*Not legal advice — this is a plain-English explanation of why this project is structured the
way it is, for readers' context, not a legal opinion for your specific situation. Consult a
lawyer if you need one.*

## Short version

Nothing in this repository required bypassing any access control, encryption, authentication, or
DRM. The firmware update file and the app's JavaScript bundle documented here are both served in
the clear, over plain HTTPS, to any requester — the same way they're served to Focus V's own
official app. Downloading and reading a file your browser can already fetch, and writing down
what you learned, isn't circumvention of anything.

Where reverse engineering *is* the relevant legal question — interoperability work, building a
compatible independent client — U.S. law has a specific, on-point carve-out for exactly that.

## The relevant statute

**[17 U.S.C. § 1201](https://www.law.cornell.edu/uscode/text/17/1201)** — the DMCA's
anti-circumvention provisions — is the U.S. law most often invoked against reverse-engineering
work. It prohibits circumventing a *technological measure that effectively controls access* to a
copyrighted work (§ 1201(a)(1)), and trafficking in tools designed to do so (§ 1201(a)(2),
§ 1201(b)).

Two things matter for this project specifically:

1. **§ 1201 only applies where a technological protection measure exists to circumvent in the
   first place.** A firmware update manifest and app bundle served to any anonymous HTTP request,
   with no login, no signed request, no encryption to defeat, isn't protected by such a measure —
   there's nothing here that the statute's prohibition reaches.
2. **§ 1201(f)** — the reverse-engineering exemption — separately and explicitly permits
   circumventing a technological measure "for the sole purpose of identifying and analyzing those
   elements of the program that are necessary to achieve interoperability of an independently
   created computer program with other programs," where that information isn't otherwise readily
   available, and permits developing and sharing the resulting interoperability information for
   that purpose. That's a precise description of what this repository is: analysis and
   documentation aimed at letting independent software talk to hardware you already own, not
   circumvention of a paywall or DRM system.

Reverse engineering for interoperability also sits on a long line of legal precedent outside
§ 1201 as well (most notably *Sega v. Accolade* and *Sony v. Connectix* in the Ninth Circuit,
addressing fair-use analysis of intermediate copying during reverse engineering) — not
reproduced here in detail since the point of this document is context, not a legal brief.

## What this means practically

- This repo documents protocol and firmware *behavior*, in the researcher's own words, citing
  specific offsets and line numbers — it does not redistribute Focus V's copyrighted binaries or
  app bundle (see the README for exactly what's excluded and why).
- The purpose throughout has been understanding and interoperating with hardware already owned by
  the people doing the research — not defeating any purchase, subscription, or access
  restriction.
- If you build something on top of this documentation, the same considerations apply to your own
  project — this document explains the reasoning behind *this* repo's scope, it isn't a blanket
  clearance for anything downstream.
