(define (problem loadbalance-p02)
  (:domain loadbalance)

  (:objects
    us_east - region
    payments search - service
    s1_us s2_us - server
    b1 b2 b3 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_us us_east)

    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 us_east)

    (bucket-service b1 payments)
    (bucket-service b2 payments)
    (bucket-service b3 search)

    (online s1_us)
    (online s2_us)

    (runs s1_us payments)
    (runs s2_us search)

    (unassigned b1)
    (unassigned b2)
    (unassigned b3)

    (= (capacity s1_us) 3)
    (= (capacity s2_us) 3)
    (= (load s1_us) 0)
    (= (load s2_us) 0)
  )

  ;; Canonical goal: payments buckets on s1_us, search on s2_us
  (:goal
    (and
      (assigned-to b1 s1_us)
      (assigned-to b2 s1_us)
      (assigned-to b3 s2_us)
    )
  )

  (:metric minimize (total-cost))
)