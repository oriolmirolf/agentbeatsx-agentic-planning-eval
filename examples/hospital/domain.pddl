(define (domain hospital)
  (:requirements :strips :typing :negative-preconditions :disjunctive-preconditions :fluents)
  (:types
    patient bed ward
  )

  (:predicates
    (patient-ward ?p - patient ?w - ward)       ; required ward type for patient
    (bed-ward ?b - bed ?w - ward)               ; ward of bed
    (isolation-required ?p - patient)           ; patient needs isolation
    (isolation-bed ?b - bed)                    ; bed is isolation-capable

    (waiting ?p - patient)                      ; patient is waiting for admission
    (in-bed ?p - patient ?b - bed)              ; patient currently in bed
    (discharged ?p - patient)                   ; patient has been discharged

    (bed-free ?b - bed)                         ; bed is empty and usable
    (bed-dirty ?b - bed)                        ; bed needs cleaning before use
    (bed-blocked ?b - bed)                      ; bed unavailable (maintenance, reserved)

  ) 

  (:functions
    (total-cost)
  )

  ;; Admit a waiting patient into a suitable bed.
  (:action admit
    :parameters (?p - patient ?b - bed ?w - ward)
    :precondition (and
      (waiting ?p)
      (not (discharged ?p))
      (bed-free ?b)
      (not (bed-dirty ?b))
      (not (bed-blocked ?b))
      (patient-ward ?p ?w)
      (bed-ward ?b ?w)
      (or (not (isolation-required ?p)) (isolation-bed ?b))
    )
    :effect (and
      (not (waiting ?p))
      (in-bed ?p ?b)
      (not (bed-free ?b))
      (increase (total-cost) 1)
    )
  )

  ;; Move a patient from one bed to another.
  (:action transfer
    :parameters (?p - patient ?from - bed ?to - bed ?w - ward)
    :precondition (and
      (in-bed ?p ?from)
      (bed-free ?to)
      (not (bed-dirty ?to))
      (not (bed-blocked ?to))
      (patient-ward ?p ?w)
      (bed-ward ?to ?w)
      (or (not (isolation-required ?p)) (isolation-bed ?to))
    )
    :effect (and
      (in-bed ?p ?to)
      (not (in-bed ?p ?from))
      (bed-dirty ?from)
      (not (bed-free ?to))
      (increase (total-cost) 1)
    )
  )

  ;; Discharge a patient from a bed, leaving the bed dirty.
  (:action discharge
    :parameters (?p - patient ?b - bed)
    :precondition (in-bed ?p ?b)
    :effect (and
      (discharged ?p)
      (not (in-bed ?p ?b))
      (bed-dirty ?b)
      (increase (total-cost) 1)
    )
  )

  ;; Clean a dirty bed, making it usable again.
  (:action clean-bed
    :parameters (?b - bed)
    :precondition (and
      (bed-dirty ?b)
      (not (bed-blocked ?b))
    )
    :effect (and
      (not (bed-dirty ?b))
      (bed-free ?b)
      (increase (total-cost) 1)
    )
  )

  ;; Block a free bed (e.g., maintenance or reservation).
  (:action block-bed
    :parameters (?b - bed)
    :precondition (and
      (bed-free ?b)
      (not (bed-blocked ?b))
    )
    :effect (and
      (bed-blocked ?b)
      (not (bed-free ?b))
      (increase (total-cost) 1)
    )
  )

  ;; Unblock a bed, making it free.
  (:action unblock-bed
    :parameters (?b - bed)
    :precondition (bed-blocked ?b)
    :effect (and
      (not (bed-blocked ?b))
      (bed-free ?b)
      (increase (total-cost) 1)
    )
  )
)
