(define (domain gripper)
  (:requirements :strips :typing :negative-preconditions :fluents)
  (:types room ball gripper)

  (:predicates
    (at-robot ?r - room)
    (at ?b - ball ?r - room)
    (free ?g - gripper)
    (carry ?b - ball ?g - gripper)
  )

  (:functions (total-cost))

  (:action move
    :parameters (?from - room ?to - room)
    :precondition (at-robot ?from)
    :effect (and
      (not (at-robot ?from))
      (at-robot ?to)
      (increase (total-cost) 1)
    )
  )

  (:action pick
    :parameters (?b - ball ?r - room ?g - gripper)
    :precondition (and
      (at-robot ?r)
      (at ?b ?r)
      (free ?g)
    )
    :effect (and
      (carry ?b ?g)
      (not (at ?b ?r))
      (not (free ?g))
      (increase (total-cost) 1)
    )
  )

  (:action drop
    :parameters (?b - ball ?r - room ?g - gripper)
    :precondition (and
      (at-robot ?r)
      (carry ?b ?g)
    )
    :effect (and
      (at ?b ?r)
      (free ?g)
      (not (carry ?b ?g))
      (increase (total-cost) 1)
    )
  )
)
