(define (problem loadbalance-p01)
  (:domain loadbalance)

  (:objects
    eu_west - region
    search  - service
    s1_eu s2_eu - server
    b1 b2 b3 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_eu eu_west)
    (server-region s2_eu eu_west)

    (bucket-region b1 eu_west)
    (bucket-region b2 eu_west)
    (bucket-region b3 eu_west)

    (bucket-service b1 search)
    (bucket-service b2 search)
    (bucket-service b3 search)

    (online s1_eu)
    (online s2_eu)

    (runs s1_eu search)
    (runs s2_eu search)

    (assigned-to b1 s1_eu)
    (assigned-to b2 s2_eu)
    (unassigned b3)

    (= (capacity s1_eu) 3)
    (= (capacity s2_eu) 3)
    (= (load s1_eu) 1)
    (= (load s2_eu) 1)
  )

  ;; All buckets on s1_eu, s2_eu powered off
  (:goal
    (and
      (assigned-to b1 s1_eu)
      (assigned-to b2 s1_eu)
      (assigned-to b3 s1_eu)
      (online s1_eu)
      (not (online s2_eu))
    )
  )

  (:metric minimize (total-cost))
)