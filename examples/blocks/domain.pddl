;; Blocksworld domain inspired by standard STRIPS formulation
;; The domain defines five predicates to describe the state of blocks and the robot arm.
;; Four actions are available: pick‑up, put‑down, stack and unstack.  Each action
;; requires certain preconditions and has additive and delete effects.  See the
;; referenced lecture notes for details【789902751098195†L118-L198】.

(define (domain blocksworld)
  (:requirements :strips)
  (:predicates
    ;; object ?x is on object ?y
    (on ?x ?y)
    ;; ?x is directly on the table
    (on-table ?x)
    ;; ?x has nothing on top of it
    (clear ?x)
    ;; the robot’s arm is not holding anything
    (arm-empty)
    ;; the robot’s arm is holding ?x
    (holding ?x)
  )

  ;; pick‑up removes a block from the table
  (:action pick-up
    :parameters (?ob)
    :precondition (and (clear ?ob) (on-table ?ob) (arm-empty))
    :effect (and
      (not (on-table ?ob))
      (not (clear ?ob))
      (not (arm-empty))
      (holding ?ob)))

  ;; put‑down places a held block back on the table
  (:action put-down
    :parameters (?ob)
    :precondition (holding ?ob)
    :effect (and
      (not (holding ?ob))
      (clear ?ob)
      (arm-empty)
      (on-table ?ob)))

  ;; stack places a held block on top of another clear block
  (:action stack
    :parameters (?ob ?under)
    :precondition (and (holding ?ob) (clear ?under))
    :effect (and
      (not (holding ?ob))
      (not (clear ?under))
      (clear ?ob)
      (arm-empty)
      (on ?ob ?under)))

  ;; unstack removes a block from atop another
  (:action unstack
    :parameters (?ob ?under)
    :precondition (and (on ?ob ?under) (clear ?ob) (arm-empty))
    :effect (and
      (holding ?ob)
      (clear ?under)
      (not (clear ?ob))
      (not (arm-empty))
      (not (on ?ob ?under))))
)