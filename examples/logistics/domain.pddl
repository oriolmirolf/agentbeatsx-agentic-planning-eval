(define (domain logistics)
  (:requirements :strips :typing :negative-preconditions :fluents)
  (:types package truck airplane city location)

  (:predicates
    (at-package ?p - package ?l - location)
    (at-truck ?t - truck ?l - location)
    (at-airplane ?a - airplane ?l - location)

    (in-truck ?p - package ?t - truck)
    (in-airplane ?p - package ?a - airplane)

    (in-city ?l - location ?c - city)
    (airport ?l - location)
  )

  (:functions (total-cost))

  ;; Trucks can drive between locations inside the same city.
  (:action drive-truck
    :parameters (?t - truck ?from - location ?to - location ?c - city)
    :precondition (and
      (at-truck ?t ?from)
      (in-city ?from ?c)
      (in-city ?to ?c)
    )
    :effect (and
      (not (at-truck ?t ?from))
      (at-truck ?t ?to)
      (increase (total-cost) 1)
    )
  )

  ;; Airplanes can fly between airports.
  (:action fly-airplane
    :parameters (?a - airplane ?from - location ?to - location)
    :precondition (and
      (at-airplane ?a ?from)
      (airport ?from)
      (airport ?to)
    )
    :effect (and
      (not (at-airplane ?a ?from))
      (at-airplane ?a ?to)
      (increase (total-cost) 1)
    )
  )

  ;; Load/unload packages into trucks.
  (:action load-truck
    :parameters (?p - package ?t - truck ?l - location)
    :precondition (and
      (at-package ?p ?l)
      (at-truck ?t ?l)
    )
    :effect (and
      (not (at-package ?p ?l))
      (in-truck ?p ?t)
      (increase (total-cost) 1)
    )
  )

  (:action unload-truck
    :parameters (?p - package ?t - truck ?l - location)
    :precondition (and
      (in-truck ?p ?t)
      (at-truck ?t ?l)
    )
    :effect (and
      (not (in-truck ?p ?t))
      (at-package ?p ?l)
      (increase (total-cost) 1)
    )
  )

  ;; Load/unload packages into airplanes (only at airports).
  (:action load-airplane
    :parameters (?p - package ?a - airplane ?l - location)
    :precondition (and
      (at-package ?p ?l)
      (at-airplane ?a ?l)
      (airport ?l)
    )
    :effect (and
      (not (at-package ?p ?l))
      (in-airplane ?p ?a)
      (increase (total-cost) 1)
    )
  )

  (:action unload-airplane
    :parameters (?p - package ?a - airplane ?l - location)
    :precondition (and
      (in-airplane ?p ?a)
      (at-airplane ?a ?l)
    )
    :effect (and
      (not (in-airplane ?p ?a))
      (at-package ?p ?l)
      (increase (total-cost) 1)
    )
  )
)
