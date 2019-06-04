"""Tests the encoding of domain information into the embedding"""

# The tests are verbose, but they are not intended to read exhaustively
# anyway. When reading particular failing examples, verbosity is good.
# pylint:disable=too-many-lines

from pytest import approx

from infrastructure import InfrastructureNetwork
from overlay import OverlayNetwork
from embedding import PartialEmbedding, ENode


def test_path_loss():
    """
    Tests that an embedding over impossible distances is recognized as
    invalid.
    """
    infra = InfrastructureNetwork()

    # Two nodes, 1km apart. The transmitting node has a transmission
    # power of 1dBm (=1.26mW). With a path loss over 1km of *at least*
    # 30dBm, less than ~-30dBm (approx. 10^-3 = 0.001mW = 1uW) arrives
    # at the target. That is a very optimistic approximation and is not
    # nearly enough to send any reasonable signal.
    source_node = infra.add_source(pos=(0, 0), transmit_power_dbm=1)
    infra.set_sink(pos=(1000, 0), transmit_power_dbm=0)

    overlay = OverlayNetwork()
    source_block = overlay.add_source()
    sink_block = overlay.set_sink()

    overlay.add_link(source_block, sink_block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(source_block, source_node)],
        sinrth=2.0,
    )
    assert len(embedding.possibilities()) == 0


def test_trivial_possibilities():
    """
    Tests that a single reasonable option is correctly generated in a
    trivial case.
    """
    infra = InfrastructureNetwork()

    # Two nodes, 1m apart. The transmitting node has a
    # transmit_power_dbm
    # power of 30dBm (similar to a regular router) which should easily
    # cover the distance of 1m without any noise.
    source_node = infra.add_source(pos=(0, 0), transmit_power_dbm=0.1)
    infra.set_sink(pos=(1, 0), transmit_power_dbm=0)

    overlay = OverlayNetwork()
    source_block = overlay.add_source()
    sink_block = overlay.set_sink()

    overlay.add_link(source_block, sink_block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(source_block, source_node)],
        sinrth=2.0,
    )
    # either go to N2 as a relay (doesn't make sense but is a viable
    # option), or embed B2 into N2 and go there
    assert len(embedding.possibilities()) == 2


def test_manually_verified_sinr():
    """
    Tests that the SINR calculation agrees with a manually verified
    example.
    """
    infra = InfrastructureNetwork()

    # 2 sources, 2 intermediaries, 1 sink
    n_source1 = infra.add_source(pos=(0, 0), transmit_power_dbm=30)
    n_interm1 = infra.add_intermediate(pos=(1, 0), transmit_power_dbm=30)
    n_source2 = infra.add_source(pos=(0, 2), transmit_power_dbm=30)
    n_interm2 = infra.add_intermediate(pos=(1, 2), transmit_power_dbm=30)
    n_sink = infra.set_sink(pos=(3, 1), transmit_power_dbm=0)

    overlay = OverlayNetwork()
    b_source1 = overlay.add_source()
    b_interm1 = overlay.add_intermediate()
    b_source2 = overlay.add_source()
    b_interm2 = overlay.add_intermediate()
    b_sink = overlay.set_sink()

    overlay.add_link(b_source1, b_interm1)
    overlay.add_link(b_source2, b_interm2)

    # just to make the embedding complete
    overlay.add_link(b_interm1, b_sink)
    overlay.add_link(b_interm2, b_sink)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(b_source1, n_source1), (b_source2, n_source2)],
    )

    # this doesn't actually do anything, just makes the next step more
    # convenient
    e_source1 = ENode(b_source1, n_source1)
    e_source2 = ENode(b_source2, n_source2)
    e_interm1 = ENode(b_interm1, n_interm1)
    e_interm2 = ENode(b_interm2, n_interm2)
    e_sink = ENode(b_sink, n_sink)

    # Here is the important part: Two signals in parallel
    embedding.take_action(e_source1, e_interm1, 0)
    embedding.take_action(e_source2, e_interm2, 0)

    # We don't really care what is going on in other timeslots, this is
    # just to make the embedding valid.
    embedding.take_action(e_interm1, e_sink, 1)
    embedding.take_action(e_interm2, e_sink, 2)

    # Now we have a clean model to work with in timeslot 1: Two parallel
    # communications, one signal and one noise.
    # Let's calculate the SINR or signal1.

    # source1 sends with 30dBm. There is a distance of 1m to interm1.
    # According to the log path loss model with a loss exponent of 4
    # (appropriate for a building), the signal will incur a loss of
    # 4 * distance_decibel dBm
    # Where distance_decibel is the distance in relation to 1m, i.e. 0
    # in this case. That means there is *no loss*, at least according to
    # the model.

    # It follows that interm1 receives a signal of 30dBm. Now on to the
    # received noise. source2 also sends with 30dBm and has a distance
    # of sqrt(1^2 + 2^2) ~= 2.24m to interm1. According to the log path
    # loss model:
    # distance_decibel = 10 * lg(2.24) ~= 3.50
    # => path_loss = 4 * 3.50 ~= 14 dBm

    # So interm1 receives roughly 16 dBm of noise. Lets assume a base
    # noise of 15dB. We have to add those two. Care must be taken here
    # because of the logarithmic scale. Naive addition would result in
    # multiplication of the actual power in watts. So we need to convert
    # back to watts first, then add, then convert back:
    # base_noise_milliwatts = 10^(1.5) ~= 31.62 mW
    # com_noise_milliwatts = 10^(1.6) ~= 39.81 mW
    # => total_noise = 31.62 + 39.81 = 71.43 mW
    # The total noise is 71.43 mW, which equals
    # 10*lg(71.43) ~= 18.54 dB
    # That is way less than the naively calculated 16 + 15 = 31 dB.

    # That means the SINR should be
    # sinr = 30dBm - 18.54dBm = 11.46dB
    # Here the subtraction actually *should* represent a division of the
    # powers.

    sinr = embedding.known_sinr(n_source1, n_interm1, 0, noise_floor_dbm=15)
    assert sinr == approx(11.46, abs=0.1)


def test_invalidating_earlier_choice_impossible():
    """
    Tests that an action that would invalidate an earlier action is
    impossible.
    """
    infra = InfrastructureNetwork()

    # Two sources, one sink. Equal distance from both sources to sink.
    # One source with moderate transmit power (but enough to cover the
    # distance, one source with excessive transmit power.
    # transmit_power_dbm
    # power of 30dBm (similar to a regular router) which should easily
    # cover the distance of 1m without any noise.
    source_node_silent = infra.add_source(
        pos=(0, 0), transmit_power_dbm=20, name="Silent"
    )
    source_node_screamer = infra.add_source(
        pos=(3, 0), transmit_power_dbm=100, name="Screamer"
    )
    node_sink = infra.set_sink(pos=(1, 3), transmit_power_dbm=0, name="Sink")

    overlay = OverlayNetwork()

    esource_silent = ENode(overlay.add_source(), source_node_silent)
    esource_screamer = ENode(overlay.add_source(), source_node_screamer)
    esink = ENode(overlay.set_sink(), node_sink)

    overlay.add_link(esource_silent.block, esink.block)
    overlay.add_link(esource_screamer.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[
            (esource_silent.block, esource_silent.node),
            (esource_screamer.block, esource_screamer.node),
        ],
        sinrth=2.0,
    )

    action_to_be_invalidated = (esource_screamer, esink, 0)
    # make sure the action is an option in the first place
    assert action_to_be_invalidated in embedding.possibilities()

    # embed the link from the silent node to the sink
    embedding.take_action(esource_silent, esink, 0)

    # first assert that action would be valid by itself
    screamer_sinr = embedding.known_sinr(source_node_screamer, node_sink, 0)
    assert screamer_sinr > embedding.sinrth

    new_possibilities = embedding.possibilities()
    # but since the action would make the first embedding invalid (a
    # node cannot receive two signals at the same time), it should still
    # not be possible
    assert action_to_be_invalidated not in new_possibilities

    # since there are no options left in the first timeslot, there are
    # now exactly 3 (screamer -> any other node as relay, screamer ->
    # sink embedded) options left in the newly created second timeslot
    assert len(new_possibilities) == 3


def test_no_unnecessary_options():
    """
    Tests that no unnecessary connections are offered.
    """
    infra = InfrastructureNetwork()

    # Two sources, one sink. Equal distance from both sources to sink.
    # One source with moderate transmit power (but enough to cover the
    # distance, one source with excessive transmit power.
    # transmit_power_dbm
    # power of 30dBm (similar to a regular router) which should easily
    # cover the distance of 1m without any noise.
    source_node = infra.add_source(
        pos=(0, 0), transmit_power_dbm=30, name="Source"
    )
    sink_node = infra.set_sink(pos=(1, 3), transmit_power_dbm=0, name="Sink")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(), source_node)
    esink = ENode(overlay.set_sink(), sink_node)

    overlay.add_link(esource.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    # Currently, it would be possible to either embed the sink and
    # directly link to it, or to use the sink as a relay (although that
    # wouldn't make much sense).
    assert len(embedding.possibilities()) == 2

    # embed the sink
    embedding.take_action(esource, esink, 0)

    # Now it would still be *feasible* according to add a connection to
    # the relay in the other timeslot. It shouldn't be possible however,
    # since all outgoing connections are already embedded.
    assert len(embedding.possibilities()) == 0


def test_all_viable_options_offered():
    """
    Tests that all manually verified options are offered in a concrete
    example.
    """
    infra = InfrastructureNetwork()

    # Two sources, one sink, one intermediate, one relay
    # Enough transmit power so that it doesn't need to be taken into account
    nsource1 = infra.add_source(
        pos=(0, 0),
        # transmit power should not block anything in this example
        transmit_power_dbm=100,
        name="N1",
    )
    nsource2 = infra.add_source(pos=(1, 0), transmit_power_dbm=100, name="N2")
    _nrelay = infra.add_intermediate(
        pos=(0, 1), transmit_power_dbm=100, name="N3"
    )
    ninterm = infra.add_intermediate(
        pos=(2, 0), transmit_power_dbm=100, name="N4"
    )
    nsink = infra.set_sink(pos=(1, 1), transmit_power_dbm=100, name="N5")

    overlay = OverlayNetwork()

    esource1 = ENode(overlay.add_source(), nsource1)
    esource2 = ENode(overlay.add_source(), nsource2)
    einterm = ENode(overlay.add_intermediate(), ninterm)
    esink = ENode(overlay.set_sink(), nsink)

    # source1 connects to the sink over the intermediate source2
    # connects both to the sink and to source1.
    overlay.add_link(esource1.block, einterm.block)
    overlay.add_link(einterm.block, esink.block)
    overlay.add_link(esource2.block, esink.block)
    overlay.add_link(esource2.block, esource1.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[
            (esource1.block, esource1.node),
            (esource2.block, esource2.node),
        ],
        sinrth=2.0,
    )

    # source1 can connect to the intermediate, which could be embedded
    # in any node (5). It could also connect to any other node as a
    # relay (4) -> 9. source2 can connect to the sink (1) or the other
    # source (1).  It could also connect to any other node as a relay
    # (4) -> 6 No timeslot is used yet, so there is just one timeslot
    # option.
    assert len(embedding.possibilities()) == 9 + 6


def test_timeslots_dynamically_created():
    """Tests the dynamic creation of new timeslots as needed"""
    infra = InfrastructureNetwork()

    nsource1 = infra.add_source(
        pos=(0, 0),
        # transmits so loudly that no other node can realistically
        # transmit in the same timeslot
        transmit_power_dbm=1000,
    )
    nsource2 = infra.add_source(pos=(1, 0), transmit_power_dbm=1000)
    nsink = infra.set_sink(pos=(1, 1), transmit_power_dbm=1000)

    overlay = OverlayNetwork()

    esource1 = ENode(overlay.add_source(), nsource1)
    esource2 = ENode(overlay.add_source(), nsource2)
    esink = ENode(overlay.set_sink(), nsink)

    overlay.add_link(esource1.block, esink.block)
    overlay.add_link(esource2.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[
            (esource1.block, esource1.node),
            (esource2.block, esource2.node),
        ],
        sinrth=2.0,
    )

    # nothing used yet
    assert embedding.used_timeslots == 0

    # it would be possible to create a new timeslot and embed either
    # link in it (2) or go to a relay from either source (2 * 2)
    assert len(embedding.possibilities()) == 6

    # Take an action. nosurce1 will transmit so strongly that nsource2
    # cannot send at the same timelot
    assert embedding.take_action(esource1, esink, 0)

    # timeslot 0 is now used
    assert embedding.used_timeslots == 1

    # New options (for creating timeslot 1) were created accordingly.
    # The seconds source could now still send to two different relays or
    # to the sink directly, it will just have to do it in a new
    # timeslot.
    assert len(embedding.possibilities()) == 3


def test_completion_detection():
    """
    Tests that the completeness of an embedding is accurately detected
    in a simple example.
    """
    infra = InfrastructureNetwork()

    # One source, one sink, one relay.
    # Enough transmit power so that it doesn't need to be taken into account
    nsource = infra.add_source(
        pos=(0, 0),
        # transmit power should not block anything in this example
        transmit_power_dbm=100,
    )
    _nrelay = infra.add_intermediate(pos=(0, 1), transmit_power_dbm=100)
    nsink = infra.set_sink(pos=(1, 1), transmit_power_dbm=100)

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(), nsource)
    esink = ENode(overlay.set_sink(), nsink)

    overlay.add_link(esource.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert not embedding.is_complete()

    embedding.take_action(esource, esink, 0)

    assert embedding.is_complete()


def test_parallel_receive_impossible():
    """
    Tests that receiving from two sender nodes at the same time is
    impossible
    """
    infra = InfrastructureNetwork()

    nsource1 = infra.add_source(pos=(0, 0), transmit_power_dbm=30)
    nsource2 = infra.add_source(pos=(3, 0), transmit_power_dbm=30)
    nsink = infra.set_sink(pos=(2, 0), transmit_power_dbm=30)

    overlay = OverlayNetwork()

    esource1 = ENode(overlay.add_source(), nsource1)
    esource2 = ENode(overlay.add_source(), nsource2)
    esink = ENode(overlay.set_sink(), nsink)

    # two incoming connections to sink
    overlay.add_link(esource1.block, esink.block)
    overlay.add_link(esource2.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[
            (esource1.block, esource1.node),
            (esource2.block, esource2.node),
        ],
        sinrth=2.0,
    )

    # Try to send two signals to sink at the same timeslot. This should
    # fail, as either one signal should overshadow the other.
    embedding.take_action(esource1, esink, 0)
    assert not embedding.take_action(esource2, esink, 0)


def test_broadcast_possible():
    """Tests that broadcast is possible despite SINR constraints"""
    infra = InfrastructureNetwork()

    # One source, one sink, one intermediate
    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=30)
    ninterm = infra.add_intermediate(pos=(1, 2), transmit_power_dbm=30)
    nsink = infra.set_sink(pos=(2, 0), transmit_power_dbm=30)

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(), nsource)
    einterm = ENode(overlay.add_intermediate(), ninterm)
    esink = ENode(overlay.set_sink(), nsink)

    # fork
    overlay.add_link(esource.block, einterm.block)
    overlay.add_link(esource.block, esink.block)

    # make complete
    overlay.add_link(einterm.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    # Broadcast from source to sink and intermediate
    sinr_before = embedding.known_sinr(esource.node, esink.node, timeslot=0)
    assert embedding.take_action(esource, esink, 0)
    power_at_sink = embedding.power_at_node(esink.node, 0)
    assert embedding.take_action(esource, einterm, 0)

    # Make sure the broadcasting isn't counted twice
    assert embedding.power_at_node(esink.node, 0) == power_at_sink

    # Make sure the broadcasts do not interfere with each other
    assert sinr_before == embedding.known_sinr(
        esource.node, esink.node, timeslot=0
    )


def test_count_timeslots_multiple_sources():
    """Tests correct counting behaviour with multiple sources"""
    infra = InfrastructureNetwork()

    nsource1 = infra.add_source(pos=(0, -1), transmit_power_dbm=30)
    nsource2 = infra.add_source(pos=(0, 1), transmit_power_dbm=30)
    nsink = infra.set_sink(pos=(1, 0), transmit_power_dbm=30)

    overlay = OverlayNetwork()

    esource1 = ENode(overlay.add_source(), nsource1)
    esource2 = ENode(overlay.add_source(), nsource2)
    esink = ENode(overlay.set_sink(), nsink)

    overlay.add_link(esource1.block, esink.block)
    overlay.add_link(esource2.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[
            (esource1.block, esource1.node),
            (esource2.block, esource2.node),
        ],
        sinrth=2.0,
    )

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 0

    assert embedding.take_action(esource1, esink, 0)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 1

    assert embedding.take_action(esource2, esink, 1)

    assert embedding.is_complete()
    assert embedding.used_timeslots == 2


def test_count_timeslots_parallel():
    """Tests correct counting behaviour with parallel connections"""
    infra = InfrastructureNetwork()

    # One source, one sink, two intermediates
    nsource = infra.add_source(
        pos=(0, 0), transmit_power_dbm=30, name="nsource"
    )
    ninterm1 = infra.add_intermediate(
        pos=(1, 2), transmit_power_dbm=30, name="ninterm1"
    )
    ninterm2 = infra.add_intermediate(
        pos=(1, -2), transmit_power_dbm=30, name="ninterm2"
    )
    nsink = infra.set_sink(pos=(2, 0), transmit_power_dbm=30, name="nsink")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bsource"), nsource)
    einterm1 = ENode(overlay.add_intermediate(name="binterm1"), ninterm1)
    einterm2 = ENode(overlay.add_intermediate(name="binterm2"), ninterm2)
    esink = ENode(overlay.set_sink(name="bsink"), nsink)

    # fork
    overlay.add_link(esource.block, einterm1.block)
    overlay.add_link(esource.block, einterm2.block)

    overlay.add_link(einterm1.block, esink.block)
    overlay.add_link(einterm2.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 0

    assert embedding.take_action(esource, einterm1, 0)
    assert embedding.take_action(esource, einterm2, 0)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 1

    assert embedding.take_action(einterm1, esink, 1)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 2

    assert embedding.take_action(einterm2, esink, 2)

    assert embedding.is_complete()
    assert embedding.used_timeslots == 3


def test_count_timeslots_loop():
    """Tests reasonable counting behaviour with loops"""
    infra = InfrastructureNetwork()

    # One source, one sink, two intermediates
    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=30, name="nso")
    ninterm1 = infra.add_intermediate(
        pos=(2, 1), transmit_power_dbm=5, name="ni1"
    )
    ninterm2 = infra.add_intermediate(
        pos=(0, -1), transmit_power_dbm=5, name="ni2"
    )
    nsink = infra.set_sink(pos=(2, 0), transmit_power_dbm=30, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    einterm1 = ENode(overlay.add_intermediate(name="bi1"), ninterm1)
    einterm2 = ENode(overlay.add_intermediate(name="bi2"), ninterm2)
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    overlay.add_link(esource.block, einterm1.block)
    overlay.add_link(einterm1.block, esink.block)
    overlay.add_link(esink.block, einterm2.block)
    overlay.add_link(einterm2.block, esource.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 0

    assert embedding.take_action(esource, einterm1, 0)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 1

    assert embedding.take_action(einterm1, esink, 1)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 2

    assert embedding.take_action(esink, einterm2, 2)

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 3

    assert embedding.take_action(einterm2, esource, 1)

    assert embedding.is_complete()
    assert embedding.used_timeslots == 3


def test_relays_correctly_wired_up():
    """
    Tests that if an connection to a relay is selected, the relay is
    correctly copied and wired up.
    """
    infra = InfrastructureNetwork()

    # One source, one sink, two relays
    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=1, name="nso")
    nrelay1 = infra.add_intermediate(
        pos=(10, 0), transmit_power_dbm=1, name="nrelay1"
    )
    nrelay2 = infra.add_intermediate(
        pos=(20, 0), transmit_power_dbm=1, name="nrelay2"
    )
    nsink = infra.set_sink(pos=(30, 0), transmit_power_dbm=1, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    overlay.add_link(esource.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert not embedding.is_complete()
    assert embedding.used_timeslots == 0

    assert set(embedding.possibilities()) == set(
        [
            (esource, esink, 0),
            (esource, ENode(None, nsink), 0),
            (esource, ENode(None, nrelay1), 0),
            (esource, ENode(None, nrelay2), 0),
        ]
    )

    assert embedding.take_action(esource, ENode(None, nrelay1), 0)

    erelay1_source = ENode(None, nrelay1, predecessor=esource)
    assert set(embedding.possibilities()) == set(
        [
            (erelay1_source, esink, 1),
            (erelay1_source, ENode(None, nsource), 1),
            (erelay1_source, ENode(None, nsink), 1),
            (erelay1_source, ENode(None, nrelay2), 1),
        ]
    )

    assert embedding.take_action(erelay1_source, ENode(None, nrelay2), 1)
    erelay2_source = ENode(None, nrelay2, predecessor=erelay1_source)
    assert set(embedding.possibilities()) == set(
        [
            (erelay2_source, esink, 2),
            (erelay2_source, ENode(None, nsource), 2),
            (erelay2_source, ENode(None, nsink), 2),
            (erelay2_source, ENode(None, nrelay1), 2),
        ]
    )


def test_outlinks_limited():
    """
    Tests that the number of possible outlinks is limited by the number
    of outlinks to embed for that block.
    """
    # raise Exception()
    infra = InfrastructureNetwork()

    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=1, name="nso")
    nrelay = infra.add_intermediate(
        pos=(1, 0), transmit_power_dbm=1, name="nr"
    )
    # The sink is way out of reach, embedding is not possible
    nsink = infra.set_sink(pos=(1, 1), transmit_power_dbm=1, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    overlay.add_link(esource.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert embedding.take_action(esource, ENode(None, nrelay), 0)

    print(embedding.possibilities())
    possibilities_from_source = [
        (source, target, timeslot)
        for (source, target, timeslot) in embedding.possibilities()
        if source == esource
    ]
    # the source block has one outgoing edge, one outlink is already
    # embedded (although the link is not embedded completely)
    assert len(possibilities_from_source) == 0

    possibilities_from_relay = [
        (source, target, timeslot)
        for (source, target, timeslot) in embedding.possibilities()
        if source == ENode(None, nrelay, esource)
    ]
    # yet the link can be continued from the relay
    assert len(possibilities_from_relay) > 0


def test_loop_within_infra_possible():
    """
    Tests that a loop within the infrastructure is always possible and
    does not interfere with other connections. This can be used to embed
    multiple consecutive blocks within one node.
    """
    infra = InfrastructureNetwork()

    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=30, name="nso")
    nsink = infra.set_sink(pos=(1, 0), transmit_power_dbm=30, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    einterm = ENode(overlay.add_intermediate(name="bin"), nsource)
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    overlay.add_link(esource.block, einterm.block)
    overlay.add_link(einterm.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    sinr_before = embedding.known_sinr(nsource, nsink, 0)
    assert embedding.take_action(esource, einterm, 0)
    sinr_after = embedding.known_sinr(nsource, nsink, 0)
    assert sinr_before == sinr_after

    assert embedding.take_action(einterm, esink, 0)
    assert embedding.is_complete()


def test_big_distance_not_solvable():
    """Tests that an embedding is not solvable if the sink is not
    reachable from a source"""
    infra = InfrastructureNetwork()

    # those nodes cannot possibly reach each other
    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=1, name="nso")
    nsink = infra.set_sink(pos=(100000, 0), transmit_power_dbm=1, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    # so this link cannot be embedded
    overlay.add_link(esource.block, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert not embedding.is_solvable()


def test_more_blocks_than_nodes_solvable():
    """Tests that an embedding with many blocks but only two nodes is
    solvable as long as those two nodes can reach each other"""

    infra = InfrastructureNetwork()

    # those nodes cannot possibly reach each other
    nsource = infra.add_source(pos=(0, 0), transmit_power_dbm=1, name="nso")
    nsink = infra.set_sink(pos=(1, 0), transmit_power_dbm=30, name="nsi")

    overlay = OverlayNetwork()

    esource = ENode(overlay.add_source(name="bso"), nsource)
    binterm = overlay.add_intermediate(name="bin")
    esink = ENode(overlay.set_sink(name="bsi"), nsink)

    # one link will just have to be embedded within a node
    overlay.add_link(esource.block, binterm)
    overlay.add_link(binterm, esink.block)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(esource.block, esource.node)],
        sinrth=2.0,
    )

    assert embedding.is_solvable()


def test_link_edges_cannot_be_embedded_twice():
    """Tests that edges completing a link that is already embedded are
    removed or not even added when creating a new timestep"""
    infra = InfrastructureNetwork()
    nso = infra.add_source(pos=(0, 0), transmit_power_dbm=30, name="nso")
    nsi = infra.set_sink(pos=(2, 0), transmit_power_dbm=30, name="nsi")
    nint = infra.add_intermediate(
        pos=(1, -1), transmit_power_dbm=30, name="nint"
    )

    overlay = OverlayNetwork()
    bso = overlay.add_source(name="bso")
    bsi = overlay.set_sink(name="bsi")
    bint = overlay.add_intermediate("bint")

    overlay.add_link(bso, bsi)
    overlay.add_link(bso, bint)
    overlay.add_link(bint, bsi)

    embedding = PartialEmbedding(
        infra, overlay, source_mapping=[(bso, nso)], sinrth=2.0
    )

    eso = ENode(bso, nso)
    esi = ENode(bsi, nsi)
    # now the link from source to sink is already embedded, only the one
    # from source to intermediate should be left
    assert embedding.take_action(eso, esi, 0)

    # so embedding it again should not be possible
    assert not embedding.take_action(ENode(bso, nso), ENode(bsi, nsi), 1)

    # and not via relay either
    assert embedding.take_action(eso, ENode(None, nint), 0)
    assert not embedding.take_action(
        ENode(None, nint, eso), ENode(bsi, nsi), 1
    )


def test_unnecessary_links_removed_in_other_timeslots():
    """
    Tests that links in other timeslots are removed if they are embedded
    in one timeslot.
    """
    infra = InfrastructureNetwork()

    nfaraway_1 = infra.add_source(
        pos=(999999998, 99999999), transmit_power_dbm=5, name="nfaraway_1"
    )
    nfaraway_2 = infra.add_intermediate(
        pos=(999999999, 99999999), transmit_power_dbm=5, name="nfaraway_2"
    )

    nsi = infra.set_sink(pos=(9, 5), transmit_power_dbm=12, name="nsi")
    nso = infra.add_source(pos=(8, 3), transmit_power_dbm=3, name="nso")

    overlay = OverlayNetwork()

    bsi = overlay.set_sink(name="bsi")
    bso = overlay.add_source(name="bso")
    bfaraway_1 = overlay.add_source(name="bfaraway_1")
    bfaraway_2 = overlay.add_intermediate(name="bfaraway_2")

    overlay.add_link(bso, bsi)
    overlay.add_link(bfaraway_1, bfaraway_2)
    # just to make it correct
    overlay.add_link(bfaraway_2, bsi)

    embedding = PartialEmbedding(
        infra,
        overlay,
        source_mapping=[(bso, nso), (bfaraway_1, nfaraway_1)],
        sinrth=2.0,
    )

    esi = ENode(bsi, nsi)
    eso = ENode(bso, nso)
    efaraway_1 = ENode(bfaraway_1, nfaraway_1)
    efaraway_2 = ENode(bfaraway_2, nfaraway_2)

    # make sure a second timeslot is created
    assert embedding.take_action(efaraway_1, efaraway_2, 0)

    # make sure embedding is possible in ts1
    assert (eso, esi, 1) in embedding.possibilities()

    # embed the link in ts 0
    assert embedding.take_action(eso, esi, 0)

    # now no embedding in another timeslot should be possible anymore
    possible_outlinks_from_eso = [
        pos for pos in embedding.possibilities() if pos[0] == eso
    ]
    assert len(possible_outlinks_from_eso) == 0


def test_used_relays_not_for_other_nodes():
    """Tests that already used relay nodes are not possible actions for
    other nodes"""
    infra = InfrastructureNetwork()

    nso1 = infra.add_source(pos=(0, 0), transmit_power_dbm=30, name="nso1")
    nrelay = infra.add_intermediate(
        pos=(1, -1), transmit_power_dbm=30, name="nrelay"
    )
    nso2 = infra.add_source(pos=(1, 1), transmit_power_dbm=30, name="nso2")
    infra.set_sink(pos=(2, 0), transmit_power_dbm=30, name="nsink")

    overlay = OverlayNetwork()

    bso1 = overlay.add_source(name="bso1")
    bso2 = overlay.add_source(name="bso2")
    bsi = overlay.set_sink(name="bsi")

    overlay.add_link(bso1, bsi)
    overlay.add_link(bso2, bso1)

    embedding = PartialEmbedding(
        infra, overlay, source_mapping=[(bso1, nso1), (bso2, nso2)], sinrth=2.0
    )

    eso1 = ENode(bso1, nso1)

    # go over relay, now a relay Node (bso1)-nrelay exists
    assert embedding.take_action(eso1, ENode(None, nrelay), 0)

    possible_in_actions_to_relay = [
        pos
        for pos in embedding.possibilities()
        if pos[1] == ENode(None, nrelay, eso1)
    ]

    # no other block should be able to go over that particular relay
    # node
    assert len(possible_in_actions_to_relay) == 0


def test_remaining_outlinks_with_relays():
    """Tests that the remaining outlinks to embed detection works
    correctly with relays acting as an extension of a block"""
    infra = InfrastructureNetwork()

    nso = infra.add_source(pos=(8, 2), transmit_power_dbm=26, name="nso")
    nrelay1 = infra.add_intermediate(
        pos=(9, 8), transmit_power_dbm=4, name="nrelay1"
    )
    nrelay2 = infra.add_intermediate(
        pos=(10, 5), transmit_power_dbm=22, name="nrelay2"
    )
    nsi = infra.set_sink(pos=(6, 1), transmit_power_dbm=16, name="nsi")

    overlay = OverlayNetwork()

    bso = overlay.add_source(name="bso")
    binterm = overlay.add_intermediate(name="binterm")
    bsi = overlay.set_sink(name="bsi")

    overlay.add_link(bso, binterm)
    overlay.add_link(binterm, bsi)
    overlay.add_link(bso, bsi)

    embedding = PartialEmbedding(
        infra, overlay, source_mapping=[(bso, nso)], sinrth=2.0
    )

    eso = ENode(bso, nso)
    esi = ENode(bsi, nsi)

    def possible_targets_from(source):
        return {
            pos[1] for pos in embedding.possibilities() if pos[0] == source
        }

    # create relay node, will act as an extension of eso
    erelay2 = ENode(None, nrelay2, eso)
    assert embedding.take_action(eso, ENode(None, nrelay2), 0)
    # complete link over relay
    assert embedding.take_action(erelay2, esi, 1)

    # the relay can still be used for the second link, bso -> binterm
    assert len(possible_targets_from(erelay2)) > 0

    # embed a second outlink from eso, again to a relay
    erelay1 = ENode(None, nrelay1, eso)
    assert embedding.take_action(eso, ENode(None, nrelay1), 2)

    # it is now decided that the second link will start from eso, not
    # from the relay. There are no more links to embed from bso, so the
    # relay has no remaining outlinks.
    assert len(possible_targets_from(erelay2)) == 0

    # but the newly created relay still has options
    assert len(possible_targets_from(erelay1)) > 0
