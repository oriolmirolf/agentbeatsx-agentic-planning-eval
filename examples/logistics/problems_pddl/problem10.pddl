(define (problem logistics-p10)
  (:domain logistics)
  (:objects
    cit_1bce23 cit_4ed853 - city
    loc_174178 loc_00d56d loc_568dd1 loc_0508bc - location
    tru_b8d27c tru_77e50e - truck
    air_4f77ec - airplane
    pac_e7813b pac_342fd4 pac_71c170 pac_882714 pac_bc8807 pac_a3352d pac_39acae pac_916280 pac_238518 pac_2bce98 - package
  )
  (:init
    (= (total-cost) 0)

    ;; City membership
    (in-city loc_174178 cit_1bce23)
    (in-city loc_00d56d cit_1bce23)
    (in-city loc_568dd1 cit_4ed853)
    (in-city loc_0508bc cit_4ed853)

    ;; Airports
    (airport loc_00d56d)
    (airport loc_0508bc)

    ;; Vehicle locations
    (at-truck tru_b8d27c loc_174178)
    (at-truck tru_77e50e loc_0508bc)
    (at-airplane air_4f77ec loc_00d56d)

    ;; Packages
    (at-package pac_e7813b loc_174178)
    (at-package pac_342fd4 loc_174178)
    (at-package pac_71c170 loc_174178)
    (at-package pac_882714 loc_174178)
    (at-package pac_bc8807 loc_174178)
    (at-package pac_a3352d loc_174178)
    (at-package pac_39acae loc_174178)
    (at-package pac_916280 loc_174178)
    (at-package pac_238518 loc_174178)
    (at-package pac_2bce98 loc_174178)
  )
  (:goal (and
    (at-package pac_e7813b loc_568dd1)
    (at-package pac_342fd4 loc_568dd1)
    (at-package pac_71c170 loc_568dd1)
    (at-package pac_882714 loc_568dd1)
    (at-package pac_bc8807 loc_568dd1)
    (at-package pac_a3352d loc_568dd1)
    (at-package pac_39acae loc_568dd1)
    (at-package pac_916280 loc_568dd1)
    (at-package pac_238518 loc_568dd1)
    (at-package pac_2bce98 loc_568dd1)
  ))
  (:metric minimize (total-cost))
)
