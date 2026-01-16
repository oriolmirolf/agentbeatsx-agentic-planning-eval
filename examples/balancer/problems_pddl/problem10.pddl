(define (problem loadbalance-p10)
  (:domain loadbalance)

  (:objects
    us_east eu_west ap_south - region
    web api - service
    s1_us s2_us - server
    s3_eu s4_eu - server
    s5_ap s6_ap - server
    b1 b2 b3 b4 b5 b6 b7 b8 b9 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_us us_east)
    (server-region s3_eu eu_west)
    (server-region s4_eu eu_west)
    (server-region s5_ap ap_south)
    (server-region s6_ap ap_south)

    ;; bucket regions
    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 us_east)

    (bucket-region b4 eu_west)
    (bucket-region b5 eu_west)
    (bucket-region b6 eu_west)

    (bucket-region b7 ap_south)
    (bucket-region b8 ap_south)
    (bucket-region b9 ap_south)

    ;; bucket services
    (bucket-service b1 web)
    (bucket-service b2 web)
    (bucket-service b3 api)

    (bucket-service b4 web)
    (bucket-service b5 api)
    (bucket-service b6 api)

    (bucket-service b7 web)
    (bucket-service b8 api)
    (bucket-service b9 api)

    ;; server states
    (online s1_us)
    (online s2_us)
    (online s3_eu)
    (not (online s4_eu))
    (online s5_ap)
    (not (online s6_ap))

    ;; services:
    ;; s1_us: web + api
    (runs s1_us web)
    (runs s1_us api)

    ;; s2_us: web only
    (runs s2_us web)

    ;; s3_eu: web + api
    (runs s3_eu web)
    (runs s3_eu api)

    ;; s5_ap: web only initially
    (runs s5_ap web)

    ;; assignments
    (assigned-to b1 s1_us)
    (assigned-to b2 s1_us)
    (assigned-to b3 s1_us)

    (assigned-to b4 s3_eu)
    (assigned-to b5 s3_eu)
    (unassigned b6)

    (assigned-to b7 s5_ap)
    (unassigned b8)
    (unassigned b9)

    (= (capacity s1_us) 3)
    (= (capacity s2_us) 3)
    (= (capacity s3_eu) 3)
    (= (capacity s4_eu) 3)
    (= (capacity s5_ap) 3)
    (= (capacity s6_ap) 3)

    (= (load s1_us) 3) ; b1,b2,b3
    (= (load s2_us) 0)
    (= (load s3_eu) 2) ; b4,b5
    (= (load s4_eu) 0)
    (= (load s5_ap) 1) ; b7
    (= (load s6_ap) 0)
  )

  ;; Goal: one online server per region (canonical choice: s1_us, s3_eu, s5_ap)
  ;; and all buckets assigned in their region.
  (:goal
    (and
      ;; US-EAST: b1,b2,b3 on s1_us
      (assigned-to b1 s1_us)
      (assigned-to b2 s1_us)
      (assigned-to b3 s1_us)

      ;; EU-WEST: b4,b5,b6 on s3_eu
      (assigned-to b4 s3_eu)
      (assigned-to b5 s3_eu)
      (assigned-to b6 s3_eu)

      ;; AP-SOUTH: b7,b8,b9 on s5_ap
      (assigned-to b7 s5_ap)
      (assigned-to b8 s5_ap)
      (assigned-to b9 s5_ap)

      ;; exactly one online per region (we enforce by turning the others off)
      (online s1_us)
      (not (online s2_us))
      (online s3_eu)
      (not (online s4_eu))
      (online s5_ap)
      (not (online s6_ap))
    )
  )

  (:metric minimize (total-cost))
)