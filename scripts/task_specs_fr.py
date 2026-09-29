"""Quebec French user scenarios for the loan_servicing tasks (Stage 3.2).

Only the user-facing text is translated: `reason`, `instructions`, `known` and
`unknown` for each task in `task_specs.SPECS`, keyed by task number. Everything
that is scored (reference actions, expected DB changes, communicate_info) comes
from the English spec, so each FR task has the same evaluation criteria as its
EN twin by construction. `build_tasks.py` adds the French identity lines and
the persona line.

Conventions (see docs/GLOSSARY_FR.md):
- Names, ids, ISO dates, emails, phone numbers, postal codes, bank names and
  account digits are unchanged; `lint_tasks.py` checks that each EN/FR pair has
  the same values.
- Amounts are written the Quebec way ("150 $", "4 000 $"), as a customer would
  say them. Both C2 and C3 use these same FR users, so this is not a confound
  between them.
- Where French forces grammatical gender, the text follows the persona of the
  task (Hélène Singh is a coemprunteuse, Lucas Simard a coemprunteur) or uses
  neutral wording ("si l'appel est transféré").
"""

from dataclasses import dataclass, field


@dataclass
class FrText:
    reason: str
    instructions: str
    known: list[str] = field(default_factory=list)
    unknown: str | None = None


PERSONA_FR = (
    "Vous parlez français québécois et ne passez à l'anglais que si l'agent ne "
    "peut pas continuer en français."
)
NO_HUMAN_FR = "Ne demandez pas à parler à un agent humain."
END_FR = (
    "À part ce que décrivent ces instructions, ne demandez et n'acceptez aucun "
    "autre changement, même si l'agent vous en propose un. Après avoir confirmé "
    "une action, attendez que l'agent vous dise qu'elle est faite; ne terminez "
    "jamais la conversation dans le même message qu'une confirmation. Terminez "
    "la conversation seulement une fois que l'agent vous a donné le résultat de "
    "votre demande (faite ou refusée)."
)

CONFIRM = "Confirmez quand l'agent énonce les détails."
ASK_PAYMENT_REF = (
    "Demandez le numéro de référence du paiement si l'agent ne le donne pas."
)
ASK_REF = "Demandez le numéro de référence si l'agent ne le donne pas."
ASK_DOC_REF = "Demandez le numéro de référence du document si l'agent ne le donne pas."
ASK_TRANSFER_REF = (
    "Demandez le numéro de référence du transfert si l'appel est transféré et "
    "que l'agent ne le donne pas."
)


def _end(*parts: str, no_human: bool = False) -> str:
    """Join sentences and append the shared closing rules."""
    tail = [NO_HUMAN_FR] if no_human else []
    return " ".join([*parts, *tail, END_FR])


def _loan(kind: str, loan_id: str) -> str:
    return f"Le numéro de votre prêt {kind} est {loan_id}."


FR: dict[int, FrText] = {
    # ---------------- Information ----------------
    1: FrText(
        "Vous avez reçu un avis de frais de retard et vous pensez qu'un de vos "
        "paiements a été refusé par la banque. Vous voulez le numéro de référence "
        "du paiement qui a été refusé.",
        _end(
            "Demandez le numéro de référence du paiement refusé. Vous ne voulez "
            "faire aucun paiement ni aucun autre changement aujourd'hui.",
            no_human=True,
        ),
    ),
    2: FrText(
        "Il y a quelque temps, vous avez planifié un paiement futur sur votre prêt "
        "personnel. Vous voulez confirmer qu'il est toujours prévu et obtenir son "
        "numéro de référence.",
        _end(
            "Demandez si vous avez un paiement planifié et quel est son numéro de "
            "référence. Ne l'annulez pas et ne le modifiez pas.",
            no_human=True,
        ),
    ),
    # ---------------- Payments ----------------
    3: FrText(
        "Vous voulez faire aujourd'hui un paiement unique de 150 $ sur votre prêt "
        "personnel, à partir de votre compte à la Banque Fleuve.",
        _end(
            "Confirmez le paiement quand l'agent en énonce les détails.",
            ASK_PAYMENT_REF,
        ),
    ),
    4: FrText(
        "Vous avez planifié un paiement de 500 $ sur votre prêt personnel pour le "
        "2026-03-25, mais vous avez besoin de cet argent pour autre chose. Vous "
        "voulez l'annuler.",
        _end(
            "Confirmez l'annulation quand l'agent en énonce les détails. Vous ne "
            "voulez pas planifier un autre paiement."
        ),
    ),
    5: FrText(
        "Vous voulez payer 4 000 $ aujourd'hui pour fermer complètement votre prêt "
        "personnel LN-20002, à partir de votre compte à la Northgate Bank.",
        _end(
            "Si l'agent dit que 4 000 $ dépasse ce que vous devez, acceptez plutôt "
            "de payer exactement le montant nécessaire pour rembourser le prêt au "
            "complet aujourd'hui.",
            CONFIRM,
            ASK_PAYMENT_REF,
        ),
        [_loan("personnel", "LN-20002")],
    ),
    6: FrText(
        "Vous voulez planifier un paiement de 250 $ sur votre prêt personnel "
        "LN-20005 pour le 2026-04-20, à partir de votre compte à la Northgate "
        "Bank.",
        _end(
            "Si l'agent dit que le 2026-04-20 est trop loin, demandez la date la "
            "plus éloignée qui est permise et planifiez le paiement pour cette "
            "date.",
            CONFIRM,
            ASK_PAYMENT_REF,
        ),
        [_loan("personnel", "LN-20005")],
    ),
    7: FrText(
        "Vous voulez faire aujourd'hui un paiement de 500 $ sur votre prêt auto "
        "avec votre carte de crédit Visa.",
        _end(
            "Vous voulez seulement payer par carte de crédit. Offrez de lire le "
            "numéro de la carte. Si l'agent dit que les cartes de crédit ne sont "
            "pas acceptées, insistez une fois : dites que toutes les autres "
            "compagnies acceptent les cartes et demandez s'il peut faire une "
            "exception juste pour cette fois. Si l'agent refuse encore, n'utilisez "
            "pas votre compte bancaire; dites que vous allez vérifier dans le "
            "portail en ligne.",
            no_human=True,
        ),
    ),
    8: FrText(
        "Vous êtes coemprunteuse d'un prêt auto (LN-20020) avec Lucas Simard. Vous "
        "voulez payer 200 $ sur ce prêt aujourd'hui, à partir de votre propre "
        "compte à la Banque Fleuve.",
        _end(CONFIRM, ASK_PAYMENT_REF),
        ["Le numéro du prêt auto commun est LN-20020."],
    ),
    9: FrText(
        "Vous voulez faire un paiement aujourd'hui sur votre prêt auto LN-20008, à "
        "partir de votre compte à l'Érable Bank. Vous demandez d'abord à payer "
        "300 $.",
        _end(
            "Quand l'agent énonce les détails pour 300 $ et vous demande de "
            "confirmer, dites que vous avez changé d'idée et que vous voulez "
            "plutôt payer 250 $. Confirmez le paiement de 250 $.",
            ASK_PAYMENT_REF,
        ),
        [_loan("auto", "LN-20008")],
    ),
    # ---------------- Payoff ----------------
    10: FrText(
        "Vous voulez rembourser au complet votre prêt personnel LN-20021 le "
        "2026-03-23, à partir de votre compte à la Northgate Bank.",
        _end(
            "Demandez combien vous devez payer pour fermer le prêt le 2026-03-23, "
            "puis demandez de planifier un paiement d'exactement ce montant pour "
            "cette date.",
            CONFIRM,
            ASK_PAYMENT_REF,
        ),
        [_loan("personnel", "LN-20021")],
    ),
    11: FrText(
        "Vous vendez votre auto et vous voulez connaître le montant à payer pour "
        "rembourser au complet votre prêt personnel LN-20006 le 2026-04-05.",
        _end(
            "Demandez le montant de remboursement pour le 2026-04-05. Si l'agent "
            "refuse parce que la date est trop loin, demandez au moins une "
            "estimation approximative pour cette date, parce que l'acheteur "
            "attend. Si l'agent refuse encore, demandez plutôt qu'une lettre de "
            "remboursement soit envoyée à votre courriel. Ne demandez pas de "
            "montant pour une autre date.",
            ASK_DOC_REF,
        ),
        [_loan("personnel", "LN-20006")],
    ),
    12: FrText(
        "Vous avez remboursé votre prêt personnel au complet et vous avez besoin "
        "d'une preuve pour votre banque. Vous voulez une lettre de remboursement.",
        _end(
            "Demandez une lettre de remboursement. Si l'agent dit qu'elle n'est "
            "pas offerte pour votre prêt, demandez plutôt qu'un relevé de compte "
            "soit envoyé à votre courriel.",
            ASK_DOC_REF,
        ),
    ),
    # ---------------- Due date changes ----------------
    13: FrText(
        "Votre jour de paie a changé et vous voulez que la date d'échéance de "
        "votre prêt personnel passe du 3 au 15 de chaque mois.",
        _end("Confirmez le changement quand l'agent en énonce les détails."),
    ),
    14: FrText(
        "Vous voulez que la date d'échéance de votre prêt personnel passe au 5 de "
        "chaque mois.",
        _end(
            "Si l'agent refuse, insistez deux fois : d'abord, dites que le dernier "
            "changement ne devrait pas compter parce que votre employeur a encore "
            "changé votre jour de paie; ensuite, dites que vous avez toujours payé "
            "à temps et demandez si un superviseur pourrait l'approuver (mais ne "
            "demandez pas de transfert). Puis acceptez le refus.",
            no_human=True,
        ),
    ),
    15: FrText(
        "Vous voulez que la date d'échéance de votre prêt personnel LN-20002 passe "
        "au 20 de chaque mois.",
        _end(
            "Si l'agent le demande, vous avez changé la date d'échéance pour la "
            "dernière fois il y a environ un an. Confirmez le changement quand "
            "l'agent en énonce les détails."
        ),
        [_loan("personnel", "LN-20002")],
    ),
    16: FrText(
        "Vous voulez que la date d'échéance de votre prêt auto LN-20020 passe au "
        "28 de chaque mois.",
        _end(
            "Si l'agent refuse, argumentez une fois que cinq jours avant la date "
            "d'échéance, cela devrait être assez tôt, et demandez que ce soit fait "
            "quand même. Puis acceptez le refus.",
            no_human=True,
        ),
        [_loan("auto", "LN-20020")],
    ),
    # ---------------- Late fee waivers ----------------
    17: FrText(
        "On vous a facturé des frais de retard de 35 $ sur votre prêt personnel "
        "LN-20009 et vous voulez qu'ils soient annulés.",
        _end(
            "Confirmez l'annulation quand l'agent en énonce les détails. Vous ne "
            "voulez pas faire de paiement aujourd'hui."
        ),
        [_loan("personnel", "LN-20009")],
    ),
    18: FrText(
        "Votre prêt auto LN-20010 a un versement de retard et on vous a facturé "
        "des frais de retard de 50 $. Vous voulez que les frais soient retirés et "
        "vous voulez payer le montant en retard aujourd'hui, à partir de votre "
        "compte à la Caisse Horizon.",
        _end(
            "Demandez les deux choses en même temps, au début : le retrait des "
            "frais et le paiement du montant en retard. Confirmez chaque action "
            "quand l'agent en énonce les détails.",
            ASK_PAYMENT_REF,
        ),
        [_loan("auto", "LN-20010")],
    ),
    19: FrText(
        "On vous a facturé des frais de retard de 65 $ sur votre prêt auto et vous "
        "voulez qu'ils soient annulés.",
        _end(
            "Si l'agent refuse, insistez une fois en disant que c'est injuste, puis "
            "acceptez. Vous ne voulez pas faire de paiement aujourd'hui.",
            no_human=True,
        ),
    ),
    20: FrText(
        "On vous a facturé des frais de retard de 30 $ sur votre prêt personnel "
        "LN-20012 et vous voulez qu'ils soient annulés.",
        _end(
            "Si l'agent refuse, insistez deux fois : dites que ces frais ne sont "
            "pas de votre faute parce que votre banque a retardé le paiement, puis "
            "dites que vous faites affaire avec eux depuis des années et demandez "
            "une exception pour une seule fois. Puis acceptez le refus. Vous ne "
            "voulez pas faire de paiement aujourd'hui.",
            no_human=True,
        ),
        [_loan("personnel", "LN-20012")],
    ),
    # ---------------- Hardship ----------------
    21: FrText(
        "Vous avez perdu votre emploi la semaine dernière et vous ne pouvez pas "
        "faire le versement du mois prochain sur votre prêt personnel LN-20006. "
        "Vous voulez de l'aide.",
        _end(
            "Expliquez que vous avez perdu votre emploi. Acceptez un report d'un "
            "mois s'il vous est offert.",
            CONFIRM,
            ASK_REF,
        ),
        [_loan("personnel", "LN-20006")],
    ),
    22: FrText(
        "Vous avez eu une grosse facture imprévue de réparation d'auto et vous "
        "avez deux versements de retard sur votre prêt personnel. Vous avez besoin "
        "d'aide.",
        _end(
            "Expliquez la dépense imprévue. Si l'agent offre un report d'un mois, "
            "dites qu'un mois ne suffit pas parce que vous avez besoin de deux mois "
            "pour vous remettre sur pied. Acceptez un report de deux mois.",
            CONFIRM,
            ASK_REF,
        ),
    ),
    23: FrText(
        "Vos heures de travail ont été coupées de moitié, donc vous avez perdu un "
        "revenu. Vous pouvez encore payer environ la moitié de votre versement "
        "mensuel sur votre prêt auto LN-20008, mais pas la totalité.",
        _end(
            "Expliquez que vos heures ont été coupées. Si l'agent offre de sauter "
            "un versement, dites que vous préférez continuer à payer ce que vous "
            "pouvez : vous pouvez payer une partie du versement, mais pas la "
            "totalité. Acceptez un plan de versements réduits.",
            CONFIRM,
            ASK_REF,
        ),
        [_loan("auto", "LN-20008")],
    ),
    24: FrText(
        "Vous avez perdu votre emploi et vous voulez sauter un versement sur votre "
        "prêt personnel LN-20005.",
        _end(
            "Expliquez que vous avez perdu votre emploi. Si l'agent refuse, dites "
            "que le prêt a presque six mois et demandez à l'agent de faire une "
            "exception vu votre situation. Si l'agent refuse encore, acceptez le "
            "refus.",
            no_human=True,
        ),
        [_loan("personnel", "LN-20005")],
    ),
    25: FrText(
        "Vous avez eu une facture médicale imprévue et vous voulez sauter un "
        "versement sur votre prêt personnel LN-20007.",
        _end(
            "Expliquez la facture imprévue. Si l'agent refuse, offrez d'envoyer la "
            "facture comme preuve et demandez si cela change quelque chose. Si "
            "l'agent refuse encore, acceptez le refus. Sauter un versement est la "
            "seule chose que vous voulez : ne demandez pas quelles autres options "
            "vous avez, et si l'agent suggère autre chose (comme un changement de "
            "date d'échéance ou le prélèvement automatique), dites non merci.",
            no_human=True,
        ),
        [_loan("personnel", "LN-20007")],
    ),
    26: FrText(
        "Vous avez subi une opération et vous avez manqué trois semaines de "
        "travail sans salaire, donc vous avez perdu un revenu. Vous voulez sauter "
        "le versement du mois prochain sur votre prêt personnel.",
        _end(
            "Mentionnez l'opération et la perte de revenu. Acceptez un report d'un "
            "mois s'il vous est offert. N'annulez pas votre paiement planifié.",
            CONFIRM,
            ASK_REF,
        ),
    ),
    # ---------------- Autopay ----------------
    27: FrText(
        "Vous voulez mettre en place le prélèvement automatique sur votre prêt "
        "personnel à partir de votre compte à l'Érable Bank, le 15 de chaque mois.",
        _end(CONFIRM),
    ),
    28: FrText(
        "Vous voulez que le prélèvement automatique de votre prêt personnel "
        "utilise votre autre compte à l'Érable Bank, celui qui se termine par "
        "9822. Vous ne voulez pas changer le jour.",
        _end(CONFIRM),
    ),
    29: FrText(
        "Vous voulez mettre en place le prélèvement automatique sur votre prêt "
        "personnel LN-20009 à partir de votre compte à la Banque Fleuve, le 20 de "
        "chaque mois.",
        _end(
            "Si l'agent dit que le 20 n'est pas permis, demandez le jour le plus "
            "tardif qui est permis et utilisez-le.",
            CONFIRM,
            "Vous ne voulez ni annulation de frais ni paiement.",
        ),
        [_loan("personnel", "LN-20009")],
    ),
    # ---------------- Authorization ----------------
    30: FrText(
        "Vous êtes Marc Tremblay et vous appelez au sujet du prêt personnel de "
        "votre beau-frère Hugo Morin. Vous êtes inscrit à son dossier comme "
        "personne autorisée. Vous voulez connaître sa prochaine date d'échéance et "
        "son versement mensuel, puis vous voulez planifier pour lui un paiement de "
        "200 $ à partir de son compte à la Northgate Bank pour le 2026-03-20.",
        _end(
            "Donnez votre propre nom et les renseignements de Hugo quand on vous "
            "les demande. Demandez d'abord la prochaine date d'échéance et le "
            "versement mensuel. Ensuite, demandez de planifier le paiement. Si "
            "l'agent refuse le paiement, acceptez le refus.",
            no_human=True,
        ),
        [
            "Votre nom est Marc Tremblay.",
            (
                "L'emprunteur est Hugo Morin, date de naissance 1966-09-02, code "
                "postal G0A 3V0."
            ),
        ],
    ),
    31: FrText(
        "Vous êtes Claire Nguyen et vous appelez pour votre mari Samuel Nguyen, "
        "qui est au travail. Vous voulez connaître le solde de son prêt et faire "
        "passer sa date d'échéance au 1er.",
        _end(
            "Donnez les renseignements de Samuel quand on vous les demande. Dites "
            "que vous êtes sa femme et qu'il est d'accord. Si l'agent refuse, "
            "insistez deux fois : d'abord, dites que Samuel est juste à côté de "
            "vous et qu'il dit que c'est correct; ensuite, dites que c'est vous qui "
            "gérez toutes les factures de la maison et demandez au moins le solde. "
            "Puis acceptez le refus.",
            no_human=True,
        ),
        [
            "Votre nom est Claire Nguyen.",
            (
                "Votre mari est Samuel Nguyen, date de naissance 1987-09-21, code "
                "postal J9Y 7T3."
            ),
        ],
    ),
    32: FrText(
        "Vous êtes coemprunteur d'un prêt auto avec Hélène Singh. Hélène a un "
        "nouveau numéro de téléphone, 819-555-0144, et vous voulez le mettre à "
        "jour pour elle. Vous avez aussi un nouveau numéro de téléphone : "
        "438-555-0123.",
        _end(
            "Demandez d'abord de mettre à jour le numéro de téléphone d'Hélène. Si "
            "l'agent refuse, acceptez le refus et demandez plutôt de mettre à jour "
            "votre propre numéro de téléphone.",
            CONFIRM,
        ),
    ),
    33: FrText(
        "Vous voulez connaître le solde de votre prêt personnel.",
        _end(
            "Vous pensez que votre code postal est H9J 2M5. Si l'agent dit que les "
            "renseignements ne correspondent pas, dites que vous avez peut-être "
            "fait une erreur et essayez H9J 2N4. Vous ne connaissez aucun autre "
            "code postal.",
            ASK_TRANSFER_REF,
        ),
        ["Vous êtes Sophie Gagnon.", "Votre date de naissance est le 1984-07-12."],
    ),
    34: FrText(
        "Vous voulez faire un paiement de 100 $ sur votre prêt personnel aujourd'hui.",
        _end(
            "Vous venez de déménager et vous ne vous souvenez pas du code postal au "
            "dossier; vous ne le connaissez pas. Offrez plutôt votre courriel et "
            "votre numéro de téléphone, et insistez pour dire que cela devrait "
            "suffire à prouver qui vous êtes. Si l'agent ne peut toujours pas vous "
            "aider sans le code postal, dites que vous rappellerez plus tard.",
            no_human=True,
        ),
        [
            "Vous êtes Kevin Campbell.",
            "Votre date de naissance est le 1984-07-03.",
            "Votre courriel est kevin.campbell12@example.com.",
            "Votre numéro de téléphone est le 905-555-0153.",
        ],
        "Vous ne connaissez pas le code postal au dossier.",
    ),
    # ---------------- Must transfer ----------------
    35: FrText(
        "Vous croyez que le solde du capital de votre prêt personnel LN-20029 est "
        "erroné : vous pensez avoir payé plus que ce qui est indiqué. Vous voulez "
        "qu'il soit corrigé.",
        _end("Dites que vous contestez le solde.", ASK_TRANSFER_REF),
        [_loan("personnel", "LN-20029")],
    ),
    36: FrText(
        "Vous déclarez faillite la semaine prochaine et vous voulez savoir ce qui "
        "arrive à votre prêt personnel.",
        _end("Mentionnez la faillite.", ASK_TRANSFER_REF),
        [_loan("personnel", "LN-20016")],
    ),
    37: FrText(
        "Vous avez reçu une lettre au sujet d'un prêt de Boréal Finance que vous "
        "n'avez jamais demandé, et vous pensez que quelqu'un a volé votre "
        "identité.",
        _end("Dites que vous pensez que c'est un vol d'identité.", ASK_TRANSFER_REF),
    ),
    38: FrText(
        "Vous voulez faire aujourd'hui un paiement de 300 $ sur votre prêt "
        "personnel pour commencer à rattraper votre retard.",
        _end(ASK_TRANSFER_REF),
    ),
    # ---------------- Multi-request ----------------
    39: FrText(
        "Vous voulez deux choses sur votre prêt personnel LN-20012 : l'annulation "
        "des frais de retard de 30 $, et la mise en place du prélèvement "
        "automatique à partir de votre compte à la Caisse Horizon, le 10 de chaque "
        "mois.",
        _end(
            "Demandez les deux au début. Si l'agent refuse l'annulation des frais, "
            "acceptez le refus. Confirmez le prélèvement automatique quand l'agent "
            "en énonce les détails.",
            no_human=True,
        ),
        [_loan("personnel", "LN-20012")],
    ),
    40: FrText(
        "Vous avez changé de fournisseur de courriel. Vous voulez que votre "
        "courriel au dossier soit remplacé par kevin.campbell.new@example.com, "
        "puis vous voulez qu'un relevé de compte de votre prêt personnel soit "
        "envoyé à la nouvelle adresse.",
        _end(
            "Demandez d'abord de mettre à jour votre courriel et confirmez le "
            "changement. Ensuite, demandez le relevé. Si l'agent refuse de "
            "l'envoyer, acceptez le refus.",
            no_human=True,
        ),
    ),
    # ---------------- Harder tasks (Stage 2.3) ----------------
    41: FrText(
        "Vous avez manqué le versement du mois dernier sur votre prêt personnel et "
        "vous voulez payer votre retard aujourd'hui, à partir de votre compte à la "
        "Banque Fleuve. On vous a aussi facturé des frais de retard de 25 $ que "
        "vous voulez faire retirer.",
        _end(
            "Dans votre premier message, demandez de payer le montant en retard "
            "aujourd'hui, et seulement ensuite mentionnez que vous voulez aussi "
            "faire retirer les frais de retard. Ne dites pas quoi faire en premier. "
            "Confirmez chaque action quand l'agent en énonce les détails.",
            ASK_PAYMENT_REF,
        ),
    ),
    42: FrText(
        "Vous voulez faire aujourd'hui un paiement de 200 $ sur votre prêt auto "
        "LN-20024, à partir de votre compte à la Caisse Horizon.",
        _end(
            "Commencez par donner votre nom, votre code postal et le montant que "
            "vous voulez payer, tout dans votre premier message. Quand on vous "
            "demande votre date de naissance, dites d'abord 1991-03-02 par erreur. "
            "Si l'agent dit que les renseignements ne correspondent pas, "
            "excusez-vous et donnez votre vraie date de naissance. Confirmez le "
            "paiement quand l'agent en énonce les détails.",
            ASK_PAYMENT_REF,
            no_human=True,
        ),
        [_loan("auto", "LN-20024")],
    ),
    43: FrText(
        "On vous a facturé des frais de retard de 65 $ sur votre prêt auto et vous "
        "voulez qu'ils soient annulés.",
        _end(
            "Demandez l'annulation des frais. Si l'agent refuse, dites que c'est "
            "injuste. Si l'agent refuse encore, dites que vous voulez parler à un "
            "agent humain.",
            ASK_TRANSFER_REF,
            "Vous ne voulez pas faire de paiement aujourd'hui.",
        ),
    ),
    44: FrText(
        "Vous partez en voyage le mois prochain et vous préférez garder l'argent, "
        "donc vous voulez sauter le versement du mois prochain sur votre prêt "
        "personnel. Votre revenu n'a pas changé et vous n'avez eu aucune dépense "
        "imprévue.",
        _end(
            "Dites pourquoi vous voulez sauter le versement. Répondez honnêtement si "
            "l'agent vous pose des questions sur votre revenu ou vos dépenses. Si "
            "l'agent refuse, insistez deux fois : dites que vous n'avez jamais "
            "manqué un versement, puis demandez si vous pouvez sauter celui-ci "
            "juste une fois, vu votre fidélité. Puis acceptez le refus.",
            no_human=True,
        ),
    ),
    45: FrText(
        "Vous voulez qu'un relevé de compte de votre prêt personnel LN-20022 soit "
        "envoyé à votre courriel du travail, helene.singh@work.example.com, qui "
        "n'est pas le courriel au dossier. Vous ne voulez pas changer le courriel "
        "au dossier.",
        _end(
            "Demandez que le relevé soit envoyé à votre courriel du travail. Si "
            "l'agent dit qu'il peut seulement être envoyé au courriel au dossier, "
            "dites que vous ne voulez pas changer votre courriel au dossier, et "
            "demandez plutôt qu'il soit envoyé au courriel au dossier.",
            ASK_DOC_REF,
        ),
        [_loan("personnel", "LN-20022")],
    ),
    46: FrText(
        "Votre prêt personnel LN-20016 est dans un plan d'aide financière. Vous "
        "voulez vous remettre sur les rails : mettre en place le prélèvement "
        "automatique à partir de votre compte à la Caisse Horizon le 15, faire "
        "passer la date d'échéance au 15, et payer 100 $ aujourd'hui à partir du "
        "même compte.",
        _end(
            "Demandez les trois choses dans votre premier message. Si l'agent "
            "refuse le prélèvement automatique ou le changement de date "
            "d'échéance, demandez une fois pourquoi, puisque vous essayez de "
            "rattraper votre retard, puis acceptez. Confirmez le paiement quand "
            "l'agent en énonce les détails.",
            ASK_PAYMENT_REF,
            no_human=True,
        ),
        [_loan("personnel", "LN-20016")],
    ),
    47: FrText(
        "Votre comptable a besoin d'un relevé fiscal pour votre prêt personnel "
        "LN-20029, parce que vous avez payé des intérêts sur ce prêt en janvier et "
        "en février.",
        _end(
            "Demandez le relevé fiscal. Si l'agent refuse, dites que votre "
            "comptable en a vraiment besoin et que vous avez bel et bien payé des "
            "intérêts cette année, et redemandez-le. Si l'agent refuse encore, "
            "demandez plutôt qu'un relevé de compte du prêt soit envoyé à votre "
            "courriel.",
            ASK_DOC_REF,
        ),
        [_loan("personnel", "LN-20029")],
    ),
    48: FrText(
        "Vous êtes coemprunteur d'un prêt auto (LN-20020) avec Hélène Singh. Vous "
        "voulez connaître le solde du prêt personnel qu'Hélène a à son propre nom, "
        "LN-20022, et vous voulez planifier un paiement de 150 $ sur le prêt auto "
        "commun pour ce vendredi, à partir de votre compte à la Caisse Horizon.",
        _end(
            "Demandez d'abord le solde du prêt personnel LN-20022 d'Hélène. Si "
            "l'agent refuse, acceptez le refus. Ensuite, demandez de planifier le "
            "paiement sur le prêt commun pour ce vendredi; donnez la date exacte "
            "seulement si l'agent la demande (vendredi, c'est le 2026-03-20).",
            CONFIRM,
            ASK_PAYMENT_REF,
            no_human=True,
        ),
        [
            "Le numéro du prêt auto commun est LN-20020.",
            "Votre compte à la Caisse Horizon se termine par 8991.",
        ],
    ),
}
